from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    TELEGRAM_BOT_TOKEN: str
    LLM_API_KEY: str
    TAVILY_API_KEY: str
    WEBHOOK_URL: str
    DASHBOARD_USER_ID: int | None = None
    LLM_PROVIDER: str = "google"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    DEFAULT_SMART_MODEL: str = "deepseek-v4-flash"
    DEFAULT_FAST_MODEL: str = "deepseek-v4-flash"

    DATABASE_URL: str = "postgresql://webdocuser:webdocpassword@localhost:5433/bot_db"
    DB_DIR: str = "db"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
