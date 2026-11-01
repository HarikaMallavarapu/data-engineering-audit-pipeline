import pytest
from app.core.config import Settings
from pydantic import ValidationError


def test_settings_default_to_local_sqlite_and_frontend_origins():
    settings = Settings(_env_file=None)

    assert settings.database_url.startswith("sqlite:")
    assert settings.cors_origins == ["http://localhost:5173", "http://127.0.0.1:5173"]


@pytest.mark.parametrize("environment", ["prod", "production", "PRODUCTION"])
def test_production_settings_reject_wildcard_cors(environment: str):
    with pytest.raises(ValidationError, match="CORS_ORIGINS must not contain"):
        Settings(_env_file=None, environment=environment, cors_origins=["*"])


def test_production_settings_accept_explicit_frontend_origin():
    settings = Settings(
        _env_file=None,
        environment="production",
        cors_origins=["https://console.example.com"],
    )

    assert settings.cors_origins == ["https://console.example.com"]
