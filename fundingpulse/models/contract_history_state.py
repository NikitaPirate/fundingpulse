from typing import TYPE_CHECKING, Any, cast
from uuid import UUID

import sqlalchemy
from sqlalchemy import CheckConstraint
from sqlmodel import Field, Relationship, SQLModel

from fundingpulse.time import UtcDateTime, utc_now

if TYPE_CHECKING:
    from fundingpulse.models.contract import Contract


class ContractHistoryState(SQLModel, table=True):
    """Tracker-owned progress state for historical funding ingestion."""

    __tablename__: str = "contract_history_state"
    __table_args__ = (
        CheckConstraint(
            "history_synced = false "
            "OR (oldest_timestamp IS NOT NULL AND newest_timestamp IS NOT NULL)",
            name="contract_history_state_synced_has_bounds",
        ),
    )

    contract_id: UUID = Field(
        sa_column=sqlalchemy.Column(
            sqlalchemy.Uuid(),
            sqlalchemy.ForeignKey("contract.id", ondelete="CASCADE"),
            primary_key=True,
        )
    )
    history_synced: bool = Field(default=False, sa_column_kwargs={"server_default": "false"})
    oldest_timestamp: UtcDateTime | None = Field(
        default=None,
        sa_type=cast(Any, sqlalchemy.DateTime(timezone=True)),
    )
    newest_timestamp: UtcDateTime | None = Field(
        default=None,
        sa_type=cast(Any, sqlalchemy.DateTime(timezone=True)),
    )
    updated_at: UtcDateTime = Field(
        default_factory=utc_now,
        sa_type=cast(Any, sqlalchemy.DateTime(timezone=True)),
        sa_column_kwargs={"server_default": sqlalchemy.text("NOW()")},
    )

    contract: Contract = Relationship(
        back_populates="history_state",
        sa_relationship_kwargs={
            "lazy": "selectin",
        },
    )
