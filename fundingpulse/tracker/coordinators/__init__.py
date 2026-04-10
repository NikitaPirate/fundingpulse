"""Coordinators for orchestrating exchange data collection.

This module provides universal coordinators that work with any exchange adapter:
- contract_registry: Synchronize contract list from exchange to database
- history_fetcher: Fetch and store historical funding data
- live_collector: Collect current unsettled funding rates
"""

from fundingpulse.tracker.coordinators.contract_registry import register_contracts
from fundingpulse.tracker.coordinators.history_fetcher import sync_contract, update_contract
from fundingpulse.tracker.coordinators.live_collector import collect_live

__all__ = [
    "register_contracts",
    "sync_contract",
    "update_contract",
    "collect_live",
]
