from typing import Any, cast

import sqlalchemy
from sqlalchemy import CheckConstraint, Column, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from fundingpulse.time import UtcDateTime, utc_now


class IngestionTask(SQLModel, table=True):
    """Control-plane task state for ingestion pipelines."""

    __tablename__: str = "ingestion_task"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'done', 'failed')",
            name="ingestion_task_status_check",
        ),
        Index(
            "ix_ingestion_task_pending_claim",
            "pipeline",
            "created_at",
            postgresql_where=sqlalchemy.text("status = 'pending'"),
        ),
        Index(
            "ix_ingestion_task_active_exchange",
            "pipeline",
            "exchange_name",
            postgresql_where=sqlalchemy.text("status IN ('pending', 'running')"),
        ),
        Index(
            "ix_ingestion_task_running_claimed_at",
            "pipeline",
            "claimed_at",
            postgresql_where=sqlalchemy.text("status = 'running'"),
        ),
    )

    task_key: str = Field(primary_key=True, nullable=False)
    pipeline: str = Field(nullable=False)
    exchange_name: str = Field(nullable=False)
    scheduled_for: UtcDateTime = Field(
        nullable=False,
        sa_type=cast(Any, sqlalchemy.DateTime(timezone=True)),
    )
    payload: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, server_default=sqlalchemy.text("'{}'::jsonb"), nullable=False),
    )
    status: str = Field(nullable=False)
    created_at: UtcDateTime = Field(
        default_factory=utc_now,
        nullable=False,
        sa_type=cast(Any, sqlalchemy.DateTime(timezone=True)),
        sa_column_kwargs={"server_default": sqlalchemy.text("NOW()")},
    )
    claimed_at: UtcDateTime | None = Field(
        default=None,
        sa_type=cast(Any, sqlalchemy.DateTime(timezone=True)),
    )
    finished_at: UtcDateTime | None = Field(
        default=None,
        sa_type=cast(Any, sqlalchemy.DateTime(timezone=True)),
    )
    worker_id: str | None = None
    error_type: str | None = None
    error_message: str | None = None
