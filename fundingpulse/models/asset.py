from sqlmodel import Field

from fundingpulse.models.base import NameModel


class Asset(NameModel, table=True):
    market_cap_rank: int | None = Field(default=None, index=True)

    # Explicit hash/eq for pyright with table=True
    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Asset):
            return NotImplemented
        return self.name == other.name
