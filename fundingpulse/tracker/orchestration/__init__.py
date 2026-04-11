"""Orchestration layer for funding tracker.

Provides ExchangeOrchestrator — the complete workflow for exchange data
collection: contract registration, historical data sync/update, and live
rate collection.

The orchestration layer sits between the scheduler and exchange adapters:
- Scheduler calls simple methods: update(), update_live()
- Orchestrator handles all workflow logic internally

Example:
    orchestrator = ExchangeOrchestrator(...)
    await orchestrator.update()        # Register contracts + sync/update history
    await orchestrator.update_live()   # Collect live funding rates
"""

from fundingpulse.tracker.orchestration.exchange_orchestrator import ExchangeOrchestrator

__all__ = ["ExchangeOrchestrator"]
