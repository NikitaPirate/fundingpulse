"""Orchestration layer for funding tracker.

Provides ExchangeOrchestrator — the scheduler-facing workflow for sharded
exchange data collection: incremental history update, legacy history
sync/update, and live rate collection. Contract registration is a separate
singleton maintenance job.

The sharded orchestration layer sits between the scheduler and exchange adapters:
- Scheduler calls simple methods: update_history(), update(), update_live()
- Orchestrator delegates workflow logic to sibling modules

Example:
    orchestrator = ExchangeOrchestrator(...)
    await orchestrator.update_history()  # Incrementally update history
    await orchestrator.update()          # Legacy sync/update history
    await orchestrator.update_live()     # Collect live funding rates
"""

from fundingpulse.tracker.orchestration.exchange_orchestrator import ExchangeOrchestrator

__all__ = ["ExchangeOrchestrator"]
