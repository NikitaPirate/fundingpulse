from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, Relationship

from fundingpulse.models.base import UUIDModel

if TYPE_CHECKING:
    from fundingpulse.models.asset import Asset
    from fundingpulse.models.section import Section


class Contract(UUIDModel, table=True):
    asset_name: str = Field(foreign_key="asset.name")
    section_name: str = Field(foreign_key="section.name")
    funding_interval: int
    quote_name: str = Field(index=True)
    synced: bool = Field(default=False)
    special_fields: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON, server_default="{}")
    )
    deprecated: bool = Field(default=False, sa_column_kwargs={"server_default": "false"})

    asset: Asset = Relationship(
        back_populates="contracts",
        sa_relationship_kwargs={
            "lazy": "selectin",
        },
    )
    section: Section = Relationship(
        back_populates="contracts",
        sa_relationship_kwargs={
            "lazy": "selectin",
        },
    )

    __table_args__ = (UniqueConstraint("asset_name", "section_name", "quote_name"),)

    def __hash__(self) -> int:
        return hash(self.id)
