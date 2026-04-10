from collections.abc import Iterable, Sequence

from sqlalchemy.sql.expression import select

from fundingpulse.models.contract import Contract
from fundingpulse.tracker.db.repositories.base import Repository
from fundingpulse.tracker.db.repositories.utils import bulk_insert


class ContractRepository(Repository[Contract]):
    _model = Contract

    async def get_by_section(self, section_name: str) -> Sequence[Contract]:
        stmt = select(Contract).where(Contract.section_name == section_name)  # type: ignore[arg-type]
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_active_by_section(self, section_name: str) -> Sequence[Contract]:
        """Returns non-deprecated contracts only."""
        stmt = select(Contract).where(  # type: ignore[arg-type]
            Contract.section_name == section_name,  # type: ignore[arg-type]
            Contract.deprecated == False,  # type: ignore[arg-type]  # noqa: E712
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def upsert_many(self, contracts: Iterable[Contract]) -> None:
        """Updates funding_interval and deprecated on conflict."""
        await bulk_insert(
            self._session,
            Contract,
            contracts,
            conflict_target=["asset_name", "section_name", "quote_name"],
            on_conflict="update",
            update_fields=["funding_interval", "deprecated"],
        )
