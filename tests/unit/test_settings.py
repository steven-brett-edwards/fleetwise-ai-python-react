"""Settings-level parsing pins.

Most of `Settings` is just field declarations that pydantic-settings
exercises via its own test suite, so we only need a test here for logic
we added on top -- currently the CSV/JSON-tolerant CORS origins parser.
That one bit us in production (Render's env-var UI hands us CSV and
pydantic-settings' default JSON-only complex decoder blew up), so pin
both shapes end-to-end.
"""

from __future__ import annotations

import pytest

from fleetwise.settings import Settings


def _build(env: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> Settings:
    # Clear any .env-derived value first so test-set env vars win.
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    return Settings(_env_file=None)  # type: ignore[call-arg]


def test_cors_origins_default_covers_angular_and_vite_dev_ports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _build({}, monkeypatch)
    assert "http://localhost:4200" in settings.cors_allowed_origins
    assert "http://localhost:5173" in settings.cors_allowed_origins


def test_cors_origins_parses_comma_separated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    # Shape humans actually type in Render's env-var UI.
    settings = _build(
        {"CORS_ALLOWED_ORIGINS": "https://a.example.com,https://b.example.com"},
        monkeypatch,
    )
    assert settings.cors_allowed_origins == [
        "https://a.example.com",
        "https://b.example.com",
    ]


def test_cors_origins_parses_json_array_env(monkeypatch: pytest.MonkeyPatch) -> None:
    # Shape pydantic-settings would have wanted by default.
    settings = _build(
        {"CORS_ALLOWED_ORIGINS": '["https://a.example.com","https://b.example.com"]'},
        monkeypatch,
    )
    assert settings.cors_allowed_origins == [
        "https://a.example.com",
        "https://b.example.com",
    ]


def test_cors_origins_trims_whitespace_and_drops_empties(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _build(
        {"CORS_ALLOWED_ORIGINS": " https://a.example.com ,, https://b.example.com "},
        monkeypatch,
    )
    assert settings.cors_allowed_origins == [
        "https://a.example.com",
        "https://b.example.com",
    ]
