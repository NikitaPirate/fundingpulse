"""Unit of Work implementation for funding tracker.

Provides concrete UnitOfWork with all repositories needed for funding history tracking.
"""

from collections.abc import Callable
from types import TracebackType
from typing import Any, Self

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from fundingpulse.tracker.db.repositories import (
    AssetRepository,
    ContractRepository,
    HistoricalFundingPointRepository,
    LiveFundingPointRepository,
    QuoteRepository,
    SectionRepository,
)

# Type alias for UoW factory function
UOWFactoryType = Callable[[], "UnitOfWork"]


def setup_db_session(
    db_connection: str,
    session_kwargs: dict[str, Any] | None = None,
    engine_kwargs: dict[str, Any] | None = None,
) -> async_sessionmaker[AsyncSession]:
    """Create a SQLAlchemy async session factory."""
    session_kwargs = {"expire_on_commit": False, **(session_kwargs or {})}
    engine_kwargs = engine_kwargs or {}

    engine = create_async_engine(db_connection, **engine_kwargs)
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        **session_kwargs,
    )


def create_uow_factory(
    db_connection: str,
    session_kwargs: dict[str, Any] | None = None,
    engine_kwargs: dict[str, Any] | None = None,
) -> Callable[[], UnitOfWork]:
    """Create a factory function that produces UnitOfWork instances.

    Args:
        db_connection: Database connection string
        session_kwargs: Additional kwargs for async_sessionmaker (optional)
        engine_kwargs: Additional kwargs for create_async_engine (optional)

    Returns:
        A factory function that creates UnitOfWork instances
    """
    session_factory = setup_db_session(
        db_connection,
        session_kwargs=session_kwargs,
        engine_kwargs=engine_kwargs,
    )

    def _create_uow() -> UnitOfWork:
        return UnitOfWork(session_factory)

    return _create_uow


class UnitOfWork:
    """Unit of Work for funding tracker module.

    Encapsulates all repositories needed for funding history operations
    and manages transaction boundaries.

    Repositories:
        - assets: Crypto assets (BTC, ETH, etc.)
        - sections: Exchange/section data (Binance, Bybit, etc.)
        - contracts: Perpetual contracts for specific assets
        - historical_funding_records: Historical funding rate data points
        - live_funding_records: Real-time unsettled funding rate data
        - quotes: Quote currency data (USDT, USDC, etc.)

    Usage:
        async with uow_factory() as uow:
            asset = await uow.assets.get_by_symbol("BTC")
            contracts = await uow.contracts.get_by_asset_id(asset.id)
    """

    assets: AssetRepository
    sections: SectionRepository
    contracts: ContractRepository
    historical_funding_records: HistoricalFundingPointRepository
    live_funding_records: LiveFundingPointRepository
    quotes: QuoteRepository

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        """Initialize UnitOfWork with a session factory.

        Args:
            session_factory: SQLAlchemy async sessionmaker for creating database sessions
        """
        self._session_factory: async_sessionmaker[AsyncSession] = session_factory

    async def __aenter__(self) -> Self:
        """Initialize session and all repositories.

        Returns:
            Self: UnitOfWork instance with initialized repositories
        """
        self._session: AsyncSession = self._session_factory()

        self.assets = AssetRepository(self._session)
        self.sections = SectionRepository(self._session)
        self.contracts = ContractRepository(self._session)
        self.historical_funding_records = HistoricalFundingPointRepository(self._session)
        self.live_funding_records = LiveFundingPointRepository(self._session)
        self.quotes = QuoteRepository(self._session)

        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Handle transaction completion and cleanup.

        Automatically commits the transaction if no exception occurred,
        otherwise rolls back. Always closes the session safely.
        """
        try:
            if exc_val:
                await self.rollback()
            else:
                await self.commit()
        finally:
            await self._close()

    async def commit(self) -> None:
        """Commit the current transaction."""
        await self._session.commit()

    async def merge(self, instance: Any) -> Any:  # noqa: ANN401
        """Merge a detached instance into the current session."""
        return await self._session.merge(instance)

    async def rollback(self) -> None:
        """Roll back the current transaction."""
        await self._session.rollback()

    async def _close(self) -> None:
        """Close the session with cancellation protection.

        Uses asyncio.shield to ensure cleanup completes even if the task is cancelled,
        preventing connection leaks.
        """
        import asyncio

        await asyncio.shield(self._session.close())

    async def execute_raw(
        self, query: str, params: dict[str, Any] | tuple[Any, ...] | None = None
    ) -> object:
        """Execute raw SQL query.

        Args:
            query: SQL query string
            params: Optional query parameters

        Returns:
            Query execution result
        """
        return await self._session.execute(text(query), params)
