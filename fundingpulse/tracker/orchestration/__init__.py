"""Orchestration layer for funding tracker.

This module provides high-level orchestrators that combine coordinator operations
into simple functions for the scheduler.

The orchestration layer sits between the scheduler and coordinators:
- Scheduler calls simple methods: update(), update_live()
- Orchestrators combine coordinators for complete workflows
- Coordinators remain single-responsibility and testable

Example:
    orchestrator = ExchangeOrchestrator(...)
    await orchestrator.update()        # Register contracts + sync/update history
    await orchestrator.update_live()   # Collect live funding rates
"""

from fundingpulse.tracker.orchestration.exchange_orchestrator import ExchangeOrchestrator

__all__ = ["ExchangeOrchestrator"]
