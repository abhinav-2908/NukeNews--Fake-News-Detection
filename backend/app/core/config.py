from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

class Settings(BaseSettings):
    app_name: str = "NukeNews"
    database_url: str = "sqlite:///./nukenews.db"
    frontend_origins: str = "http://localhost:5173"
    openrouter_api_key: str | None = None
    openrouter_model: str | None = None
    search_provider: str = "bing_news"
    brave_search_api_key: str | None = None
    ocr_languages: str = "eng"
    max_upload_mb: int = 15
    max_text_chars: int = 100000
    model_path: str = "models/selected.joblib"
    metrics_path: str = "artifacts/metrics.json"
    model_config = SettingsConfigDict(env_file=Path(__file__).resolve().parents[3] / ".env", extra="ignore")

settings = Settings()
