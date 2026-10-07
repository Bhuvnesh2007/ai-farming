"""
config.py
─────────
Centralised settings loaded from environment / .env file.
All agents import from here so there is a single source of truth.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── watsonx.ai ──────────────────────────────────────────────────────────
    watsonx_api_key: str = Field(default="", alias="WATSONX_API_KEY")
    watsonx_project_id: str = Field(default="", alias="WATSONX_PROJECT_ID")
    watsonx_url: str = Field(
        default="https://us-south.ml.cloud.ibm.com", alias="WATSONX_URL"
    )
    granite_text_model: str = Field(
        default="ibm/granite-13b-instruct-v2", alias="GRANITE_TEXT_MODEL"
    )
    granite_vision_model: str = Field(
        default="ibm/granite-vision-3-2-2b", alias="GRANITE_VISION_MODEL"
    )

    # ── Weather ─────────────────────────────────────────────────────────────
    open_meteo_base_url: str = Field(
        default="https://api.open-meteo.com/v1/forecast",
        alias="OPEN_METEO_BASE_URL",
    )

    # ── Vector store ────────────────────────────────────────────────────────
    chroma_persist_dir: str = Field(
        default="./backend/vectorstore/chroma_db", alias="CHROMA_PERSIST_DIR"
    )
    chroma_collection: str = Field(
        default="farming_knowledge", alias="CHROMA_COLLECTION"
    )

    # ── App ─────────────────────────────────────────────────────────────────
    backend_host: str = Field(default="0.0.0.0", alias="BACKEND_HOST")
    backend_port: int = Field(default=8000, alias="BACKEND_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    offline_mode: bool = Field(default=False, alias="OFFLINE_MODE")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton of Settings."""
    return Settings()
