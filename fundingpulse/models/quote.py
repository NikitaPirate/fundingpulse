from fundingpulse.models.base import NameModel


class Quote(NameModel, table=True):
    ...

    # Explicit hash/eq for pyright with table=True
    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Quote):
            return NotImplemented
        return self.name == other.name
