import pytest
from pydantic import ValidationError

from backend.app.core.config import Settings


def production_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "production",
        "cookie_secure": True,
        "session_secret": "a-unique-production-secret-with-32-characters",
        "database_url": "postgresql+psycopg://app:unique-password@db:5432/recsys",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"cookie_secure": False}, "COOKIE_SECURE"),
        ({"session_secret": "short"}, "SESSION_SECRET"),
        (
            {"database_url": "postgresql+psycopg://recsys:recsys@db:5432/recsys"},
            "DATABASE_URL",
        ),
    ],
)
def test_production_rejects_insecure_defaults(
    overrides: dict[str, object], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        production_settings(**overrides)


def test_production_accepts_explicit_secure_configuration() -> None:
    settings = production_settings()

    assert settings.app_env == "production"
    assert settings.cookie_secure is True
