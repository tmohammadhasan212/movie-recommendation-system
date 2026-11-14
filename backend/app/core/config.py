from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://recsys:recsys@localhost:5432/recsys"
    redis_url: str = "redis://localhost:6379/0"
    app_env: str = "development"
    cookie_secure: bool = False
    session_secret: str = "development-only-replace-me"
    tmdb_api_token: str = ""
    tmdb_api_key: str = ""
    tmdb_api_base_url: str = "https://api.themoviedb.org/3"
    tmdb_image_base_url: str = "https://image.tmdb.org/t/p/w500"


@lru_cache
def get_settings() -> Settings:
    return Settings()
