from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship

from fundingpulse.models.base import NameModel

if TYPE_CHECKING:
    from fundingpulse.models.contract import Contract


class Asset(NameModel, table=True):
    market_cap_rank: int | None = Field(default=None, index=True)

    contracts: list[Contract] = Relationship(
        back_populates="asset",
        sa_relationship_kwargs={
            "lazy": "selectin",
        },
    )

    # Explicit hash/eq for pyright with table=True
    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Asset):
            return NotImplemented
        return self.name == other.name
