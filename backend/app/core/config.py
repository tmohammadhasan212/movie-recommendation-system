from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEVELOPMENT_SESSION_SECRET = "development-only-replace-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://recsys:recsys@localhost:5432/recsys"
    redis_url: str = "redis://localhost:6379/0"
    app_env: Literal["development", "test", "production"] = "development"
    cookie_secure: bool = False
    session_secret: str = DEVELOPMENT_SESSION_SECRET
    tmdb_api_token: str = ""
    tmdb_api_key: str = ""
    tmdb_api_base_url: str = "https://api.themoviedb.org/3"
    tmdb_image_base_url: str = "https://image.tmdb.org/t/p/w500"

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if self.app_env != "production":
            return self
        if not self.cookie_secure:
            raise ValueError("COOKIE_SECURE must be true in production")
        if (
            len(self.session_secret) < 32
            or self.session_secret == DEVELOPMENT_SESSION_SECRET
            or "replace-with" in self.session_secret
        ):
            raise ValueError("SESSION_SECRET must be a unique value of at least 32 characters")
        if "://recsys:recsys@" in self.database_url or "replace-with" in self.database_url:
            raise ValueError("DATABASE_URL must not use development or placeholder credentials")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
