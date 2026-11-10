"""Tests use their own configuration, never the developer's credentials."""

from pathlib import Path

import pytest

from guard import settings


@pytest.fixture(autouse=True)
def isolate_runtime_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "PAYPAL_CLIENT_ID",
        "PAYPAL_CLIENT_SECRET",
        "PAYPAL_BASE_URL",
        "LLM_BASE_URL",
        "LLM_API_KEY",
        "LLM_MODEL",
        "PAYGUARD_AUDIT_PATH",
    ):
        monkeypatch.delenv(key, raising=False)

    original_loader = settings.load_env_file

    def load_test_env(path: str | Path = settings.DEFAULT_ENV_PATH) -> None:
        if Path(path).resolve() != settings.DEFAULT_ENV_PATH.resolve():
            original_loader(path)

    monkeypatch.setattr(settings, "load_env_file", load_test_env)
