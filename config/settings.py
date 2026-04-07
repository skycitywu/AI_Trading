from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    # LLM
    llm_provider: str = Field(default="claude", description="claude or zhipu")
    anthropic_api_key: Optional[str] = None
    zhipu_api_key: Optional[str] = None

    # WeChat
    wechat_webhook_url: Optional[str] = None

    # Database
    database_url: str = "sqlite:///data/trading.db"

    # Scan settings
    scan_interval_minutes: int = 30
    max_candidates_per_underlying: int = 15

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
