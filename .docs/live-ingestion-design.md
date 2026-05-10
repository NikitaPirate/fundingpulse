# Live Funding Ingestion Design

## Goal

Move live funding collection out of the tracker scheduler into a dedicated pull-based ingestion pipeline.

The pipeline should collect live funding snapshots for all enabled exchanges, write them to the existing `live_funding_point` table, and expose enough reliability and observability data to understand how the pipeline behaves in production.

## Non-Goals

This design does not introduce a generic ingestion platform for every future pipeline.

It does not introduce Kafka, Bronze/Silver/Gold layers, a distributed workflow engine, or per-exchange static worker assignments.

It does not duplicate live collection alongside the existing tracker live job. The tracker live job is disabled when the new live ingestion pipeline is enabled.

## Code Ownership

The live ingestion implementation lives under `fundingpulse/ingestion/live/`.

Exchange-specific ingestion code lives under `fundingpulse/ingestion/exchanges/`.

Ingestion exchange adapters are separate from tracker exchange adapters. They should be designed for the ingestion layer's contracts instead of copying the tracker adapter interface wholesale.

The initial live ingestion adapter surface should include only what live ingestion needs.

## Runtime Topology

Live ingestion uses a shared APScheduler-based ingestion scheduler process, a bounded one-shot live enqueuer, a Postgres-backed task queue, and multiple identical live workers.

```text
APScheduler ingestion scheduler
  -> calls live enqueuer on the fixed schedule

live enqueuer
  -> creates live funding tasks for one scheduling tick

Postgres task queue
  -> stores task lifecycle and execution metadata

N universal live workers
  -> claim task
  -> fetch exchange live rates
  -> insert live_funding_point
  -> record execution result
```

Workers are universal. A worker can process a task for any enabled exchange.

Enabled exchanges come from the existing tracker exchange selection configuration, `FT_EXCHANGES`.

The scheduler runtime is intentionally thin. It owns periodic invocation, but it does not fetch exchange data and does not contain task creation semantics beyond calling pipeline-specific enqueuers.

The scheduler is shared by ingestion pipelines. The initial scheduler only runs the live funding enqueuer, but future pipelines can add their own bounded enqueuer jobs to the same scheduler process.

## Enqueuer

The live enqueuer is the scheduling core of the live ingestion pipeline.

It executes exactly one scheduling tick:

```text
live enqueuer
  -> resolve enabled exchanges from FT_EXCHANGES
  -> determine the current scheduled interval
  -> mark stale running live tasks as failed
  -> create live funding tasks according to the live scheduling invariant
  -> log scheduling result
  -> exit
```

The command must be bounded by a hard timeout. It must finish successfully or fail within that timeout.

The live enqueuer must be safe to run more than once for the same scheduled interval. If two invocations attempt to create the same task, the task idempotency key ensures that only one task is created and the duplicate creation becomes a no-op.

The enqueuer does not fully trust workers to finalize tasks. Each tick marks stale `running` live tasks as `failed` before scheduling current work. The stale threshold should be slightly larger than the worker hard timeout. This is recovery, not retry.

This keeps the scheduler runtime replaceable. APScheduler is the initial runtime, but the same bounded enqueuer can later be called by cron, a systemd timer, Kubernetes CronJob, CLI command, or manually.

## Enqueuer And Worker Boundary

The enqueuer owns scheduling decisions:

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
- If a scheduled execution would overlap with an already running execution for the same exchange, the scheduled execution is skipped.
- The next scheduled execution is created according to the original schedule, regardless of previous success, failure, or skip.

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
## Persistence Model

The task queue is backed by a Postgres `ingestion_task` table.

This table stores ingestion control-plane state, not business data and not observability history. It should support task creation, idempotency, claiming, execution ownership, and final lifecycle state.

The initial table is shaped for live ingestion, not for a generic task platform. This is intentional. Future ingestion pipelines may evolve the table with additional domain columns, such as `contract_id`, or introduce their own task storage if their execution model differs.

Live-specific scheduling rules, including the non-overlap rule for one exchange, are enforced by the live enqueuer, not by live-specific database constraints.

The initial task shape:

```text
ingestion_task
  id
  pipeline
  task_key
  exchange_name
  scheduled_for
  payload
  status
  created_at
  claimed_at
  finished_at
  worker_id
  error_type
  error_message
```

`exchange_name` and `scheduled_for` are first-class fields because live scheduling and routing depend on them. Both are required for the initial live ingestion pipeline.

`payload` is reserved for additional pipeline-specific data that is not part of the common live task identity or routing model.

The database enforces task identity with a unique task key. Pipeline-specific task keys carry the namespace, for example:

```text
live_funding_snapshot:{exchange}:{scheduled_for}
```

The database does not enforce live scheduling policy. It should not contain a live-specific uniqueness constraint such as "only one active task per exchange". That invariant belongs to the live enqueuer.

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

Live-specific scheduling rules, including the non-overlap rule for one exchange, are enforced by the live enqueuer, not by live-specific database constraints.

The initial task shape:

```text
ingestion_task
  id
  pipeline
  task_key
  exchange_name
  scheduled_for
  payload
  status
  created_at
  claimed_at
  finished_at
  worker_id
  error_type
  error_message
```

`exchange_name` and `scheduled_for` are first-class fields because live scheduling and routing depend on them. Both are required for the initial live ingestion pipeline.

`payload` is reserved for additional pipeline-specific data that is not part of the common live task identity or routing model.

The database enforces task identity with a unique task key. Pipeline-specific task keys carry the namespace, for example:

```text
live_funding_snapshot:{exchange}:{scheduled_for}
```

The database does not enforce live scheduling policy. It should not contain a live-specific uniqueness constraint such as "only one active task per exchange". That invariant belongs to the live enqueuer.

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

Status answers only whether the queue can claim, wait on, or ignore the task. Data quality and execution details are recorded separately as metrics and result fields.

The scheduler/orchestrator does not retry live tasks. Workers may perform local retries inside one claimed task according to worker execution logic.

## Reliability And Observability

Reliability and observability are first-class requirements.

Postgres stores execution state, not observability history. The database should contain task state required by the pipeline itself: task identity, lifecycle status, scheduling identity, claim/execution ownership, and other fields the service uses or can reasonably use while executing tasks.

Operational telemetry that is not needed by the pipeline is emitted as structured logs.

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

Every significant lifecycle transition should emit a structured event. Expected event families:

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

The new live ingestion pipeline replaces the tracker live job.

The initial cutover is direct: the same deployment that starts live ingestion also disables the existing tracker live job. There is no production shadow mode and no per-exchange live cutover flag in v0.

Historical update, contract registration, materialized view refresh, and other tracker jobs remain unchanged.

## Testing Strategy

Tests should focus on behavior boundaries and design invariants before implementation details.

The first test layer should cover the live enqueuer and scheduling invariant: idempotent task creation for one scheduled interval, no backlog/catch-up behavior, and skipped scheduling when an exchange already has active work.

The second test layer should cover worker execution boundaries: a claimed task is executed even when `scheduled_for` is in the past, live writes remain idempotent, failures are recorded, and required structured log events are emitted.

## Initial Implementation Scope

The initial implementation should include:

- code under `fundingpulse/ingestion/live/`;
- live ingestion exchange adapters under `fundingpulse/ingestion/exchanges/`;
- a Postgres-backed live ingestion task queue;
- an APScheduler-based ingestion scheduler process;
- a bounded live enqueuer that follows the live scheduling invariant;
- universal single-task worker processes;
- task claiming with row-level locking;
- live funding fetch and existing `live_funding_point` persistence;
- structured log events for reliability and observability;
- disabling the existing tracker live job when the new pipeline is enabled.
