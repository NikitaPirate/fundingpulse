"""Orchestration layer for funding tracker.

Provides ExchangeOrchestrator — the scheduler-facing workflow for sharded
exchange data collection: historical data sync/update and live rate collection.
Contract registration is a separate singleton maintenance job.

The sharded orchestration layer sits between the scheduler and exchange adapters:
- Scheduler calls simple methods: update(), update_live()
- Orchestrator handles all workflow logic internally

Example:
    orchestrator = ExchangeOrchestrator(...)
    await orchestrator.update()        # Sync/update history
    await orchestrator.update_live()   # Collect live funding rates
"""

from fundingpulse.tracker.orchestration.exchange_orchestrator import ExchangeOrchestrator

__all__ = ["ExchangeOrchestrator"]
