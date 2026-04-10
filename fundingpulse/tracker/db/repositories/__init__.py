"""Repository layer for database access using the Repository pattern (Variant 2)."""

from fundingpulse.tracker.db.repositories.asset import AssetRepository
from fundingpulse.tracker.db.repositories.base import Repository
from fundingpulse.tracker.db.repositories.contract import ContractRepository
from fundingpulse.tracker.db.repositories.historical_funding_point import (
    HistoricalFundingPointRepository,
)
from fundingpulse.tracker.db.repositories.live_funding_point import LiveFundingPointRepository
from fundingpulse.tracker.db.repositories.quote import QuoteRepository
from fundingpulse.tracker.db.repositories.section import SectionRepository

__all__ = [
    # Base
    "Repository",
    # Repositories
    "AssetRepository",
    "SectionRepository",
    "QuoteRepository",
    "ContractRepository",
    "HistoricalFundingPointRepository",
    "LiveFundingPointRepository",
]
