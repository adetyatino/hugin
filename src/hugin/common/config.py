"""Configuration, read once from the environment.

Every path, credential and switch the pipeline needs, in one typed object. The
rule this enforces is that nothing downstream reads ``os.environ`` directly:
a value that can be read from two places will eventually be read differently in
two places.

``REPLAY_EPOCH`` has no default on purpose — see
:mod:`hugin.common.replay` and ADR 002. Everything else has a default that works
on a laptop with the compose stack up.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from hugin.common.replay import ReplayClock, parse_epoch, parse_speed

SourceMode = Literal["real", "synthetic"]


class Settings(BaseSettings):
    """Everything the pipeline reads from the environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # -- source data ------------------------------------------------------

    #: The Volve archive. Read-only by policy; nothing in this repo writes here.
    volve_archive_dir: Path = Path("C:/Apply Kerja/DE/volve")

    #: ``real`` reads the Volve archive. ``synthetic`` reads calibrated
    #: fixtures, and anything it produces is labelled as such — SPEC.md
    #: section 10 makes that a licence condition, not a preference.
    source_mode: SourceMode = "real"

    # -- replay clock (BR-01) ---------------------------------------------

    #: Real UTC instant at which the replay starts. Required: defaulting it
    #: would make every run's output depend on the day it ran.
    replay_epoch: str = ""

    #: Field months per real day.
    replay_speed: str = "1"

    # -- object storage ---------------------------------------------------

    minio_endpoint: str = "http://localhost:9000"
    minio_root_user: str = "hugin"
    minio_root_password: SecretStr = SecretStr("change-me-before-first-run")
    minio_region: str = "us-east-1"
    minio_bucket: str = "hugin-lakehouse"

    # -- query engine -----------------------------------------------------

    trino_host: str = "localhost"
    trino_port: int = 8080
    trino_user: str = "hugin"
    trino_catalog: str = "iceberg"

    # -- local paths ------------------------------------------------------

    repo_root: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[3])

    @field_validator("replay_speed")
    @classmethod
    def _speed_must_parse(cls, value: str) -> str:
        parse_speed(value)  # raises ReplayClockError with a usable message
        return value

    # -- derived ----------------------------------------------------------

    @property
    def data_dir(self) -> Path:
        return self.repo_root / "data"

    @property
    def landing_dir(self) -> Path:
        return self.data_dir / "landing"

    @property
    def inventory_dir(self) -> Path:
        return self.data_dir / "_inventory"

    @property
    def bronze_dir(self) -> Path:
        """Where Parquet is staged before it is registered as Iceberg."""
        return self.data_dir / "bronze"

    @property
    def docs_dir(self) -> Path:
        return self.repo_root / "docs"

    @property
    def s3_bucket_uri(self) -> str:
        return f"s3://{self.minio_bucket}"

    def replay_clock(self) -> ReplayClock:
        """The BR-01 clock this configuration describes."""
        return ReplayClock(epoch=parse_epoch(self.replay_epoch), speed=parse_speed(self.replay_speed))

    def is_synthetic(self) -> bool:
        return self.source_mode == "synthetic"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """The process-wide settings. Cached so the environment is read once."""
    return Settings()
