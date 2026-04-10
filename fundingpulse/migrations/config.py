from __future__ import annotations

from importlib import resources

from alembic.config import Config


def get_script_location() -> str:
    return str(resources.files("fundingpulse.migrations"))


def get_alembic_config() -> Config:
    config = Config()
    config.set_main_option("script_location", get_script_location())
    return config
