from sqlalchemy import PrimaryKeyConstraint

from fundingpulse.models.base import BaseFundingPoint


class HistoricalFundingPoint(BaseFundingPoint, table=True):
    __tablename__: str = "historical_funding_point"

    __table_args__ = (
        PrimaryKeyConstraint("contract_id", "timestamp"),
        {
            "timescaledb_hypertable": {"time_column_name": "timestamp"},
        },
    )
