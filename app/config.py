from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    APP_NAME: str = "Multi-Tenant Project Management API"
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/mtp"
    SECRET_KEY: str = "change-this-secret-key-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    MAX_UPLOAD_BYTES: int = 10 * 1024 * 1024
    REMINDER_INTERVAL_SECONDS: int = 3600
    REMINDERS_ENABLED: bool = True
    UPLOAD_DIR: str = "uploads"
    EMAIL_NOTIFICATIONS_ENABLED: bool = False


settings = Settings()
