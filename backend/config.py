from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "ChangeGuard AI"
    debug: bool = True
    database_url: str = "sqlite+aiosqlite:///./changeguard.db"

    # ── AI engine selection ───────────────────────────────────────────────────
    # Set USE_MOCK_AI=false and provide WATSONX_* vars to enable real AI.
    use_mock_ai: bool = False

    # ── IBM watsonx.ai credentials (loaded from .env / environment) ──────────
    watsonx_apikey: str = ""
    watsonx_project_id: str = ""
    watsonx_url: str = "https://us-south.ml.cloud.ibm.com"
    # Current IBM Granite instruct model available in all watsonx.ai regions.
    # Override via WATSONX_MODEL_ID env var if your project uses a different one.
    watsonx_model_id: str = "ibm/granite-3-8b-instruct"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
