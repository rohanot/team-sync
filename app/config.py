from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    postgres_user: str = "teamsync"
    postgres_password: str = "teamsync"
    postgres_db: str = "teamsync"
    postgres_host: str = "db"
    postgres_port: int = 5432
    database_url: str = "postgresql+psycopg://teamsync:teamsync@db:5432/teamsync"
    app_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "*"
    dev_auth_secret: str = "dev-secret"
    seed_demo_data: bool = True
    redis_url: str | None = None
    realtime_presence_ttl_seconds: int = 60

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
