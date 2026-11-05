from pathlib import Path

import pytest

from guard.settings import ConfigurationError, Settings, load_env_file, load_settings


def test_env_file_sets_missing_values(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PAYPAL_CLIENT_ID", raising=False)
    monkeypatch.delenv("PAYPAL_CLIENT_SECRET", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# commentaire\nexport PAYPAL_CLIENT_ID='abc'\nPAYPAL_CLIENT_SECRET=def\n",
        encoding="utf-8",
    )

    load_env_file(env_file)

    import os

    assert os.environ["PAYPAL_CLIENT_ID"] == "abc"
    assert os.environ["PAYPAL_CLIENT_SECRET"] == "def"


def test_env_file_does_not_override_existing_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LLM_MODEL", "deja-defini")
    env_file = tmp_path / ".env"
    env_file.write_text("LLM_MODEL=autre\n", encoding="utf-8")

    load_env_file(env_file)

    import os

    assert os.environ["LLM_MODEL"] == "deja-defini"


def test_settings_refuse_non_sandbox_url() -> None:
    with pytest.raises(ConfigurationError, match="sandbox"):
        Settings(
            paypal_client_id="id",
            paypal_client_secret="secret",
            paypal_base_url="https://api-m.paypal.com",
        )


def test_settings_require_both_credentials() -> None:
    with pytest.raises(ConfigurationError):
        Settings(paypal_client_id="id")


def test_settings_defaults_to_sandbox_and_unconfigured() -> None:
    settings = Settings()

    assert settings.paypal_base_url == "https://api-m.sandbox.paypal.com"
    assert settings.paypal_configured is False
    assert settings.llm_configured is False


def test_load_settings_resolves_relative_audit_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PAYGUARD_AUDIT_PATH", "data/test-audit.jsonl")
    monkeypatch.delenv("PAYPAL_CLIENT_ID", raising=False)
    monkeypatch.delenv("PAYPAL_CLIENT_SECRET", raising=False)

    settings = load_settings(tmp_path / "absent.env")

    assert settings.audit_path.is_absolute()
    assert settings.audit_path.parts[-2:] == ("data", "test-audit.jsonl")
