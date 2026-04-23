"""Data Transfer Objects for exchange adapters."""

from dataclasses import dataclass

from fundingpulse.time import UtcDateTime


@dataclass
class ExchangeContractListing:
    asset_name: str
    quote_name: str
    funding_interval: int  # hours between funding payments
    section_name: str


@dataclass
class FundingPoint:
    rate: float  # Decimal format: 0.0001 = 0.01%
    timestamp: UtcDateTime
