from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, Relationship

from fundingpulse.models.base import NameModel

if TYPE_CHECKING:
    from fundingpulse.models.contract import Contract


class Section(NameModel, table=True):
    special_fields: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON, server_default="{}")
    )

    contracts: list[Contract] = Relationship(
        back_populates="section",
        sa_relationship_kwargs={
            "lazy": "selectin",
        },
    )
