"""Orchestration layer for funding tracker.

Provides ExchangeOrchestrator — the scheduler-facing workflow for sharded
exchange data collection: historical backfill, incremental history update, and
live rate collection. Contract registration is a separate singleton maintenance
job.

The sharded orchestration layer sits between the scheduler and exchange adapters:
- Scheduler calls simple methods: backfill_history(), update_history(), update_live()
- Orchestrator delegates workflow logic to sibling modules

Example:
    orchestrator = ExchangeOrchestrator(...)
    await orchestrator.backfill_history()  # Backfill older settled history
    await orchestrator.update_history()  # Incrementally update history
    await orchestrator.update_live()     # Collect live funding rates
"""

from fundingpulse.tracker.orchestration.exchange_orchestrator import ExchangeOrchestrator

__all__ = ["ExchangeOrchestrator"]
