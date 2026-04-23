from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field

from fundingpulse.models.base import NameModel


class Section(NameModel, table=True):
    special_fields: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON, server_default="{}")
    )
