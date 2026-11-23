"""Typed application settings — single source of truth for config."""

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed settings, read from ``RL_*`` variables only.

    No ``.env`` file is read: this tool runs inside someone else's repository, and that
    repository's own ``.env`` is not ours to load.
    """

    model_config = SettingsConfigDict(env_prefix="RL_", extra="ignore")

    embedding_provider: Literal["deterministic", "local"] = Field(
        default="deterministic",
        description="Embedder backend: deterministic (CI/test default) or local (fastembed ONNX)",
    )
