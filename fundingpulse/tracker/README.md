# Tracker

The tracker is the ingestion engine for FundingPulse. It is a long-running
APScheduler service that keeps the database aligned with exchange contract
lists, settled funding history, and current live funding snapshots.

It is deliberately built around recovery and repeatability. Exchange APIs can
fail, pagination windows can overlap, contracts can be listed or delisted at any
time, and a full historical backfill may run for long enough to be interrupted.
The tracker treats those cases as normal operating conditions.

## Runtime Flow

```mermaid
flowchart TD
    Start["Scheduler cycle"]
    Registry["Contract registry<br/>instance 0, every 5 minutes"]
    HistoryBackfill["History backfill<br/>startup +5m + hourly :05:00"]
    HistoryUpdate["History update<br/>immediate + hourly :00:05"]
    PendingBackfills["Load active unsynced contracts"]
    ForEachUpdate["Process active contracts"]
    Sync["Backfill history<br/>backward pagination"]
    UpdateGate{"Funding interval elapsed?"}
    Update["Incremental update<br/>fetch after newest point"]
    NoBackfillWork["No backfill work"]
    WaitForInterval["Wait until next interval"]
    Live["Live collection<br/>every minute"]

    Start --> Registry
    Start --> HistoryBackfill --> PendingBackfills
    PendingBackfills -- "some" --> Sync
    PendingBackfills -- "none" --> NoBackfillWork
    Start --> HistoryUpdate --> ForEachUpdate --> UpdateGate
    UpdateGate -- "yes" --> Update
    UpdateGate -- "no" --> WaitForInterval
    Start --> Live
```

Each exchange gets its own orchestrator, adapter, logger, and concurrency
semaphore. All orchestrators share the same database runtime and HTTP client
scope.

In production, tracker processes can be fanned out through supervisord. The
deployment reads `FT_INSTANCE_COUNT`, starts that many `funding-tracker`
processes, and passes `--instance-id` / `--total-instances` to each one. Each
instance then handles a deterministic shard of history and live collection.
Instance 0 owns singleton maintenance jobs: contract registry for all selected
exchanges, materialized-view refresh checks, and asset ranking updates.

## Exchange Adapter Boundary

Exchange-specific code lives behind `BaseExchange`. An adapter owns symbol
formatting, API pagination, funding interval detection, and live-rate fetching.
The tracker only depends on internal DTOs:

- `ExchangeContractListing` for available perpetual contracts.
- `FundingPoint` for historical and live funding rates.

The registry validates adapters at import time and exposes the `EXCHANGES`
mapping used by the CLI and scheduler bootstrap.

## Contract Registration

Contract registration runs as a separate maintenance job on instance 0. It asks
each selected exchange for its current contract list on startup and then every
five minutes at minutes 4, 9, ..., 59. That list is reconciled with existing
`Contract` rows:

- new contracts are inserted;
- missing contracts are marked deprecated;
- reappeared contracts are reactivated;
- funding interval changes are applied explicitly.

Live collection, history update, and history backfill read the shared database
state. If registry has not populated a section yet, those jobs skip empty
contract sets and pick them up on a later run.

## Historical Update And Backfill

Historical funding has separate incremental update and backfill workflows:

- **History update** runs on startup and hourly at `:00:05`. It fetches points
  after `newest_timestamp + 1s`. If a contract has no stored history yet, it
  fetches after `start_of_hour(now) - 1s`.
- **History backfill** runs startup +5 minutes and then hourly at `:05:00`. It
  queries only active contracts whose full history is not synced, then paginates
  them backward from `oldest_timestamp - 1s` until the exchange returns no older
  data.

Backfill and update deliberately keep separate workflow code. They look similar
because both move historical checkpoints, but they answer different policy
questions: update asks whether new settlements are due, while backfill asks
whether old history is complete. Shared code should stay limited to concrete
mechanics such as idempotent point persistence and monotonic bound updates.

Progress is stored in `ContractHistoryState`, one row per contract:

- `history_synced` tells whether full backfill completed.
- `oldest_timestamp` and `newest_timestamp` store committed bounds.
- state updates and funding point inserts happen in the same transaction.

The hot path does not derive sync progress by scanning the historical hypertable;
it reads the checkpoint row directly.

## Live Collection

Live collection runs every minute. It fetches current unsettled funding rates for
active contracts and stores them separately from settled historical data. This
keeps live snapshots queryable without mixing them with final funding payments.

Live jobs are intentionally simple and stateless. A failed minute is logged and
the next minute collects a fresh snapshot.

## Crash Recovery

The tracker assumes interruption can happen at any point:

| Crash point | Next run behavior |
| --- | --- |
| Contract registration | Fetches contracts again and reconciles idempotently |
| History update | Fetches from the last committed `newest_timestamp`, or from current-hour start for empty history |
| Historical backfill | Uses `oldest_timestamp` and repeats the last safe window |
| Live collection | Waits for the next minute and writes a new snapshot |

Funding points use `(contract_id, timestamp)` as the identity. Bulk inserts
ignore conflicts, so retrying overlapping windows is safe.

## Verification Tool

`verify` checks exchange adapters against real exchange APIs without starting
the scheduler or touching the database:

```bash
uv run verify hyperliquid
uv run verify --list
uv run verify --all
```

It validates the adapter protocol, fetches contracts, samples historical data,
and checks live-rate fetching. Use it after changing an adapter or when an
exchange API appears to drift.
