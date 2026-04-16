"""DTO models for funding data endpoints."""

from uuid import UUID

from pydantic import BaseModel


class FundingPoint(BaseModel):
    """A single funding rate point."""

    timestamp: int
    funding_rate: float
    contract_id: UUID


class CumulativeFundingDifference(BaseModel):
    asset_name: str
    contract_1_id: UUID
    contract_1_section: str
    contract_1_quote: str
    contract_1_total_funding: float
    contract_2_id: UUID
    contract_2_section: str
    contract_2_quote: str
    contract_2_total_funding: float
    difference: float
    abs_difference: float
    aligned_from: int
    aligned_to: int


class FundingRateDifference(BaseModel):
    asset_name: str
    contract_1_id: UUID
    contract_1_section: str
    contract_1_quote: str
    contract_1_funding_rate: float
    contract_2_id: UUID
    contract_2_section: str
    contract_2_quote: str
    contract_2_funding_rate: float
    difference: float
    abs_difference: float


class PaginatedResponse[T](BaseModel):
    data: list[T]
    total_count: int
    offset: int
    limit: int
    has_more: bool


class PaginatedFundingRateDifference(PaginatedResponse[FundingRateDifference]):
    pass


class PaginatedCumulativeFundingDifference(PaginatedResponse[CumulativeFundingDifference]):
    pass


class LatestFundingPoint(BaseModel):
    contract_id: UUID
    asset_name: str
    section_name: str
    quote_name: str
    funding_interval: int
    funding_rate: float | None
    timestamp: int | None


class HistoricalAvgWindow(BaseModel):
    days: int
    funding_rate: float | None
    points_count: int
    expected_count: int
    oldest_timestamp: int | None


class HistoricalAvgEntry(BaseModel):
    contract_id: UUID
    asset_name: str
    section_name: str
    quote_name: str
    funding_interval: int
    windows: list[HistoricalAvgWindow]


class HistoricalSumsWindow(BaseModel):
    days: int
    funding_rate: float | None
    points_count: int
    expected_count: int
    oldest_timestamp: int | None


class HistoricalSumsEntry(BaseModel):
    contract_id: UUID
    asset_name: str
    section_name: str
    quote_name: str
    funding_interval: int
    windows: list[HistoricalSumsWindow]


class FundingWallAsset(BaseModel):
    asset: str
    market_cap_rank: int | None
    rates: dict[str, float | None]


class FundingWallResponse(BaseModel):
    timestamp: int
    assets: list[FundingWallAsset]
    exchanges: list[str]
