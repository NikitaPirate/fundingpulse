"""DTOs for live ingestion exchange adapters."""

from dataclasses import dataclass

from fundingpulse.time import UtcDateTime


@dataclass(frozen=True, slots=True)
class FundingPoint:
    """Funding point returned by a live exchange adapter."""

    rate: float
    timestamp: UtcDateTime
