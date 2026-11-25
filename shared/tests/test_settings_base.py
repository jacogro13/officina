import pytest
from pydantic import ValidationError

from settings_base import AppSettings

DB_VARS = ("DATABASE_URL", "DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD", "DB_NAME", "LOG_LEVEL")


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in DB_VARS:
        monkeypatch.delenv(name, raising=False)


def test_db_parts_build_the_url_with_an_escaped_password(monkeypatch):
    monkeypatch.setenv("DB_HOST", "db")
    monkeypatch.setenv("DB_USER", "famiglia_app")
    monkeypatch.setenv("DB_PASSWORD", "p@ss/word")
    monkeypatch.setenv("DB_NAME", "famiglia_db")

    url = AppSettings().sqlalchemy_url()

    assert url == "postgresql://famiglia_app:p%40ss%2Fword@db:5432/famiglia_db"


def test_driver_applies_to_db_parts(monkeypatch):
    monkeypatch.setenv("DB_PASSWORD", "x")
    monkeypatch.setenv("DB_NAME", "chatbot_db")

    url = AppSettings().sqlalchemy_url(driver="postgresql+asyncpg")

    assert url.startswith("postgresql+asyncpg://")


def test_database_url_wins_over_db_parts(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:1/d")
    monkeypatch.setenv("DB_PASSWORD", "ignored")
    monkeypatch.setenv("DB_NAME", "ignored")

    assert AppSettings().sqlalchemy_url() == "postgresql://u:p@h:1/d"


@pytest.mark.parametrize("present", [{}, {"DB_NAME": "d"}, {"DB_PASSWORD": "p"}])
def test_missing_database_config_is_an_error(monkeypatch, present):
    for name, value in present.items():
        monkeypatch.setenv(name, value)

    with pytest.raises(ValidationError, match="DATABASE_URL"):
        AppSettings()


def test_password_is_hidden_when_settings_are_printed(monkeypatch):
    monkeypatch.setenv("DB_PASSWORD", "hunter2")
    monkeypatch.setenv("DB_NAME", "d")

    assert "hunter2" not in repr(AppSettings())


@pytest.mark.parametrize(("raw", "expected"), [("debug", "DEBUG"), ("Warning", "WARNING")])
def test_log_level_is_case_insensitive(monkeypatch, raw, expected):
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.setenv("LOG_LEVEL", raw)

    assert AppSettings().log_level == expected


def test_unknown_log_level_is_an_error(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.setenv("LOG_LEVEL", "verbose")

    with pytest.raises(ValidationError):
        AppSettings()
