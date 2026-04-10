import datetime
import uuid

import sqlalchemy
from sqlmodel import Field, SQLModel


class UUIDModel(SQLModel, table=False):
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True,
        nullable=False,
        sa_column_kwargs={"server_default": sqlalchemy.text("gen_random_uuid()"), "unique": True},
    )


class NameModel(SQLModel, table=False):
    name: str = Field(primary_key=True, index=True, unique=True)

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, NameModel):
            return NotImplemented
        return self.name == other.name


class BaseFundingPoint(SQLModel, table=False):
    timestamp: datetime.datetime
    contract_id: uuid.UUID = Field(foreign_key="contract.id")
    funding_rate: float  # Decimal format: 0.0001 = 0.01%

    def __hash__(self) -> int:
        return hash((self.contract_id, self.timestamp))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BaseFundingPoint):
            return NotImplemented
        return self.contract_id == other.contract_id and self.timestamp == other.timestamp
