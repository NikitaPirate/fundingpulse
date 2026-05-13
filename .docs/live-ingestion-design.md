# Live Funding Ingestion Design

## Goal

Start the migration from the current monolithic tracker into an ingestion/data-pipeline architecture.

Live funding is the first pipeline because it has the smallest useful boundary: minute cadence, existing `live_funding_point` storage, no contract registration ownership, and no historical sync checkpoint ownership.

The target pipeline should collect live funding snapshots for all enabled exchanges, write them to the existing `live_funding_point` table, and emit structured logs that make the service understandable in production.

This is not a standalone live subsystem. It is the first step toward moving tracker responsibilities into ingestion piece by piece. The existing tracker is the source of current behavior; implementation agents should inspect `fundingpulse/tracker/` when they need exact DB runtime, adapter, persistence, or deployment context. Exchange selection is now a shared configuration boundary, not tracker-owned behavior.

Current implementation status: phases 1, 2, and 3 are implemented. The code can store ingestion task state, schedule live funding tasks for one enqueue tick, and execute the core worker lifecycle around claimed tasks. It does not yet run a standalone scheduler process, run a worker polling loop, fetch exchange data, or write `live_funding_point` rows.

## Non-Goals

This design does not introduce Kafka, Bronze/Silver/Gold layers, a distributed workflow engine, or per-exchange static worker assignments.

It does not migrate the whole tracker in one step. Historical update, contract registration, materialized view refresh, and auxiliary tracker jobs stay in the existing tracker until their own migration phases.

It does not duplicate live collection alongside the existing tracker live job. The tracker live job is disabled when the new live ingestion pipeline is enabled.

## Code Ownership

Common ingestion code lives under `fundingpulse/ingestion/`.

The live ingestion implementation lives under `fundingpulse/ingestion/live/`.

Exchange-specific ingestion code lives under `fundingpulse/ingestion/exchanges/`.

Ingestion exchange adapters are separate from tracker exchange adapters. Their shared base should be introduced when real live execution is implemented, using the tracker adapters as the behavioral reference instead of inventing an interface before it is exercised.

The initial live ingestion adapter surface should include only what live ingestion needs.

Common ingestion code should emerge from concrete pipeline use-cases. The first stable common boundary is the `ingestion_task` schema. Enqueuer, worker, execution, and adapter interfaces should be introduced by the phases that implement those behaviors, not predeclared as a generic ingestion framework.

Ingestion-owned settings use the `FI_*` namespace and follow the repository's existing settings layout rules. Shared data-collection settings stay outside service prefixes; enabled exchange selection is owned by `ENABLED_EXCHANGES`. As of phase 2, live enqueue knobs exist as runtime-independent config objects with defaults; `FI_*` environment-backed settings should be introduced when scheduler or worker runtime wiring needs them.

## Runtime Topology

Live ingestion uses an ingestion scheduler process, pipeline-specific enqueuer jobs, a Postgres-backed task queue, and multiple identical live workers.

```text
ingestion scheduler process
  -> owns APScheduler runtime
  -> calls enqueuer jobs on their schedules

live funding enqueuer job
  -> creates live funding tasks for one scheduling tick

Postgres task queue
  -> stores task lifecycle and execution state

N universal live workers
  -> claim task
  -> fetch exchange live rates
  -> insert live_funding_point
  -> record execution result
```

Workers are universal. A worker can process a task for any enabled exchange.

Enabled exchanges come from the shared `ENABLED_EXCHANGES` setting. The parser and resolver live outside tracker runtime code so ingestion can resolve its own exchange registry without importing tracker.

`ENABLED_EXCHANGES` uses comma-separated exchange IDs. Empty or unset means all exchanges supported by the running service. Explicit unknown or duplicate exchange IDs are configuration errors, not warnings and not a fallback to all exchanges.

The scheduler process is intentionally thin. It owns periodic invocation, but it does not fetch exchange data and does not contain task creation semantics beyond calling registered enqueuer jobs.

APScheduler is the initial runtime inside the scheduler process. This is not a hard architectural dependency: the same enqueuer jobs can later be called by cron, a systemd timer, Kubernetes CronJob, CLI command, or manually.

## Enqueuer Jobs

An enqueuer job is a bounded scheduling use-case for one ingestion pipeline. In v0, define the live enqueuer by its behavior and database effects first; extract a common enqueuer abstraction only after more than one real enqueuer needs it.

Each enqueuer job:

- executes one scheduling tick;
- applies pipeline-specific scheduling rules;
- creates `ingestion_task` rows;
- performs maintenance for its task type;
- logs the scheduling result;
- exits within its timeout.

In v0, the scheduler process registers one enqueuer job: the live funding enqueuer job.

```text
live funding enqueuer job
  -> resolve enabled exchanges from runtime-supplied selection
  -> determine the current scheduled interval
  -> mark stale running live tasks as failed
  -> create live funding tasks according to the live scheduling invariant
  -> log scheduling result
  -> exit
```

The live funding enqueuer job must be bounded by a hard timeout, default 45 seconds. It must finish successfully or fail within that timeout.

The enqueuer itself accepts resolved service/runtime inputs. Later scheduler runtime wiring should build those inputs from `ENABLED_EXCHANGES` and the ingestion exchange registry, rather than making the enqueuer own environment loading.

For live funding, `scheduled_for` is the current UTC minute bucket with seconds and microseconds set to zero.

The live funding enqueuer job must be safe to run more than once for the same scheduled interval. If two invocations attempt to create the same task, the task idempotency key ensures that only one task is created and the duplicate creation becomes a no-op.

The live funding enqueuer job does not fully trust workers to finalize tasks. Each tick marks stale `running` live tasks as `failed` before scheduling current work. The stale threshold should be derived from the worker hard timeout, initially `task_timeout + 15 seconds`. This is recovery, not retry.

## Enqueuer And Worker Boundary

The enqueuer job owns scheduling decisions:

- whether a task should be created for the current tick;
- whether a scheduled execution should be skipped because the exchange already has active work;
- which `scheduled_for` value identifies the task.

The worker owns execution after claiming a task:

- it does not make scheduling decisions;
- it does not backfill missed live intervals;
- it does not skip a claimed task because `scheduled_for` is in the past;
- it executes the claimed task with a hard timeout and records the result.

`scheduled_for` identifies the scheduled interval. It is not a worker-side freshness deadline. If a task scheduled for `12:00:00` is claimed at `12:00:30`, the worker executes it and records the delay as execution metadata.

## Task Model

One task represents one live funding snapshot for one exchange and one scheduled minute.

```text
LiveFundingSnapshotTask
  pipeline = "live_funding"
  exchange = "bybit"
  scheduled_for = "2026-05-08T12:34:00Z"
```

The task is exchange-level, not contract-level. Most live funding adapters use batch exchange APIs, so the exchange is the natural unit of work.

Each task has an idempotency key:

```text
live_funding_snapshot:{exchange}:{scheduled_for}
```

## Live Scheduling Invariant

Live data represents the current moment. A missed live interval is missed forever; it does not create ingestion debt.

Live ingestion follows these scheduling rules:

- Live ingestion follows a fixed schedule.
- A failed execution does not change the schedule.
- Live data is not backfilled. The system does not create or preserve backlog for missed live intervals.
- If a scheduled execution would overlap with active work for the same exchange, the scheduled execution is skipped.
- The next scheduled execution is created according to the original schedule, regardless of previous success, failure, or skip.

For live funding, active work means an existing `pending` or `running` task for the same pipeline and exchange.

## Worker Execution Model

The initial worker model is one task per worker process.

The default initial worker count is `ceil(enabled_exchanges / 3)`, with a minimum of one worker. This is a first-iteration deployment default, not an architectural invariant.

```text
supervisord
  live-worker-00
  live-worker-01
  live-worker-02
  live-worker-03
```

Each worker follows a simple loop:

```text
while running:
  task = claim_next_task()
  if no task: sleep small interval
  execute task with hard timeout
  record execution result
```

This gives process-level isolation. A slow exchange occupies one worker slot, while other workers continue processing other exchanges.

Internal worker concurrency is not part of the initial design. If needed later, a worker-level concurrency option can be added, but the default model remains one task at a time.

## Persistence Model

The task queue is backed by a Postgres `ingestion_task` table.

This table stores ingestion control-plane state, not business data and not observability history. It should support task creation, idempotency, claiming, execution ownership, and final lifecycle state.

The initial table is shaped for live ingestion, not for a generic task platform. This is intentional. Future ingestion pipelines may evolve the table with additional domain columns, such as `contract_id`, or introduce their own task storage if their execution model differs.

Live-specific scheduling rules, including the non-overlap rule for one exchange, are enforced by the live funding enqueuer job, not by live-specific database constraints.

The initial task shape:

```text
ingestion_task
  task_key text primary key
  pipeline text not null
  exchange_name text not null
  scheduled_for timestamptz not null
  payload jsonb not null default '{}'
  status text not null
  created_at timestamptz not null default now()
  claimed_at timestamptz null
  finished_at timestamptz null
  worker_id text null
  error_type text null
  error_message text null
```

`exchange_name` and `scheduled_for` are first-class fields because live scheduling and routing depend on them. Both are required for the initial live ingestion pipeline.

`payload` is reserved for additional pipeline-specific data that is not part of the common live task identity or routing model.

The database enforces task identity with `task_key` as the primary key. Pipeline-specific task keys carry the namespace, for example:

```text
live_funding_snapshot:{exchange}:{scheduled_for}
```

The database does not enforce live scheduling policy. It should not contain a live-specific uniqueness constraint such as "only one active task per exchange". That invariant belongs to the live funding enqueuer job.

`status` should be stored as text with a check constraint, not as a Postgres enum. Initial statuses are `pending`, `running`, `done`, and `failed`.

Initial indexes:

```text
(pipeline, created_at) WHERE status = 'pending'
  claim path for worker polling

(pipeline, exchange_name) WHERE status IN ('pending', 'running')
  active-work checks for live scheduling

(pipeline, claimed_at) WHERE status = 'running'
  stale-running recovery
```

The task table intentionally does not include a surrogate `id` in the initial schema. The idempotency key is stable task identity, and using it as the primary key avoids maintaining both a UUID primary-key index and a unique task-key index. If later phases add child tables such as task attempts or task event history, a surrogate key can be reconsidered with that concrete relationship in view.

The corresponding SQLModel is exported from `fundingpulse.models`, and the migration is `009_ingestion_task.py`.

## Queue Semantics

Workers claim pending tasks with row-level locking:

```sql
SELECT ...
FROM ingestion_task
WHERE status = 'pending'
  AND pipeline = 'live_funding'
ORDER BY created_at
FOR UPDATE SKIP LOCKED
LIMIT 1;
```

The task lifecycle status is control-plane state:

```text
pending
running
done
failed
```

Status answers only whether the queue can claim, wait on, or ignore the task. Data quality and execution details are recorded separately as structured log events.

The scheduler process and enqueuer job do not retry live tasks. Workers may perform local retries inside one claimed task according to worker execution logic.

## Reliability And Observability

Reliability and observability are first-class requirements.

Postgres stores execution state, not observability history. Operational telemetry that is not needed by the pipeline is emitted as structured logs.

The live ingestion service is responsible for structured log events. It does not own Loki, Grafana, dashboards, alerts, or log shipping configuration.

The pipeline should make it possible to answer:

- which live snapshots were scheduled;
- which tasks were claimed by workers;
- which worker executed each task;
- how long queue wait, fetch, and persist phases took;
- how many contracts were expected, received, and written;
- which errors occurred;
- whether the worker performed local retries;
- which scheduled executions were skipped;
- which exchanges are slow or unreliable.

Task status should not encode result quality such as partial coverage or empty responses. Those details belong in structured log events.

Every significant lifecycle transition should emit a structured event. Phase 2 emits enqueue-level events; worker and real-execution phases should add claim, fetch, persist, and completion events. Expected event families:

```text
live_enqueue_started
live_task_created
live_task_skipped
live_enqueue_completed
live_enqueue_failed
live_task_claimed
live_fetch_started
live_fetch_completed
live_fetch_failed
live_persist_completed
live_task_completed
live_task_failed
```

Structured log fields should include the context needed to connect events for one task and understand its outcome: pipeline name, task key, exchange, `scheduled_for`, worker identity when applicable, durations, counts, local retry information, and error type/message when applicable.

The exact event and field set may be refined during implementation as the code exposes better boundaries and names. The requirement is stable structured telemetry, not this document's first draft of field names.

Live funding writes remain idempotent. `live_funding_point` continues to use conflict-ignored inserts, so a repeated execution cannot create duplicate points for the same `(contract_id, timestamp)`.

## Cutover From Tracker

The new live ingestion pipeline replaces only the tracker live job.

The initial cutover is direct: the same deployment that starts live ingestion also disables the existing tracker live job. There is no production shadow mode and no per-exchange live cutover flag in v0.

Historical update, contract registration, materialized view refresh, and other tracker jobs remain unchanged.

This is a temporary mixed architecture: live runs through ingestion, while the rest of tracker still runs through the existing tracker scheduler. Later phases should move those remaining tracker responsibilities into ingestion with their own pipeline-specific scheduling and task boundaries.

## Testing Strategy

Tests should focus on behavior boundaries and design invariants, not implementation details. For new ingestion code, first establish the production boundary, then add focused tests for the observable behavior that boundary promises.

The first test layer should cover the live funding enqueuer job and scheduling invariant: idempotent task creation for one scheduled interval, no backlog/catch-up behavior, and skipped scheduling when an exchange already has active work.

The second test layer should cover worker execution boundaries: a claimed task is executed even when `scheduled_for` is in the past, live writes remain idempotent, failures are recorded, and required structured log events are emitted.

Tests should not verify APScheduler, SQLAlchemy, Postgres locking, or httpx behavior as third-party contracts. Verify how FundingPulse uses those tools: task creation idempotency, lifecycle transitions, exchange selection behavior, and emitted structured lifecycle events.

## Implementation Roadmap

Implementation phases should be scoped by behavioral boundary and approximate size. Target around 500 changed lines per phase. High-risk or design-heavy phases can be smaller, around 250 lines. Mechanical or generic phases can be larger, up to around 1000 lines, when the boundary is already clear.

0. **Preflight Extraction And DRY Review**

   Review existing tracker code before adding ingestion code. Extract only shared pieces ingestion needs immediately and that should survive tracker removal, such as exchange selection parsing or DB runtime config helpers. Do not extract tracker-only logging helpers or perform speculative abstractions.

1. **Task Schema Foundation — Completed**

   Implemented the durable database boundary for ingestion work: `ingestion_task` SQLModel, migration `009_ingestion_task.py`, model export, and this document update. The table uses `task_key` as the primary key, stores task lifecycle state as text with a check constraint, and includes partial indexes for pending claim, active-work checks, and stale-running recovery. This phase intentionally did not add scheduler runtime, worker loops, exchange adapters, settings helpers, log constants, or speculative protocols.

2. **Live Enqueuer — Completed**

   Implemented the live funding scheduling use-case end to end. It resolves a runtime-supplied exchange selection, computes the current UTC minute bucket, marks stale running live tasks as failed, checks active work per exchange, and inserts live tasks idempotently through `task_key`. It emits enqueue-level structured events and returns a `LiveEnqueueResult` summary. This phase intentionally did not add scheduler runtime, worker claiming/execution, exchange adapters, exchange IO, or `live_funding_point` writes.

3. **Live Worker Lifecycle — Completed**

   Implemented the worker lifecycle around the task table. The code claims one pending live task with row-level locking, executes a supplied task handler outside the claim transaction, enforces worker timeout, and marks the task `done` or `failed`. It emits worker lifecycle structured events and proves claim, completion, failure, timeout, and "old scheduled tasks still execute" behavior without exchange IO or `live_funding_point` writes.

4. **Real Live Execution**

   Implement the handler for claimed live funding tasks. It loads active contracts for the task exchange, fetches current live rates, persists `LiveFundingPoint` rows with conflict-ignored inserts, and records execution counts and errors through structured logs. Introduce the ingestion exchange adapter base here, guided by the tracker adapter behavior and shared funding point shape.

5. **Scheduler Runtime**

   Wire APScheduler to call the live enqueuer on the minute schedule. The scheduler process remains thin: it owns periodic invocation and timeout handling, not task creation semantics or exchange IO.

6. **Worker Runtime**

   Add the live worker process entrypoint and one-task-at-a-time loop. Use the worker count deployment default of `ceil(enabled_exchanges / 3)` with a minimum of one process.

7. **Adapter Parity**

   Port live exchange behavior into `fundingpulse/ingestion/exchanges/` until ingestion covers the exchanges selected by `ENABLED_EXCHANGES`. Prove the adapter base with at least one batch exchange and one per-contract exchange before porting the rest.

8. **Runtime And Cutover**

   Wire the ingestion scheduler and live workers into deployment, disable the tracker live job, and run an end-to-end smoke check for enqueue -> claim -> fetch -> persist -> complete.
