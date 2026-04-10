"""Data Transfer Objects for exchange adapters."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class ContractInfo:
    asset_name: str
    quote: str
    funding_interval: int  # hours between funding payments
    section_name: str


@dataclass
class FundingPoint:
    rate: float  # Decimal format: 0.0001 = 0.01%
    timestamp: datetime
