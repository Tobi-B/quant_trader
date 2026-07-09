"""Application settings via pydantic-settings."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    data_dir: Path = Path("./data")
    universe_presets_path: Path = Path("./config/universe_presets.yaml")
    strategies_config_path: Path = Path("./config/strategies.yaml")
    db_path: Path = Path("./quant_trader.sqlite")
    log_level: str = "INFO"
    alphavantage_key: str = ""
    stockdata_api_token: str = ""


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
