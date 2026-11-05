"""Configuration locale de PayGuard.

Le chargement ne dépend d'aucune librairie externe : un fichier `.env`
minimal suffit. La seule contrainte de sécurité non négociable est que
l'URL PayPal reste celle de la sandbox.
"""

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[1]
DEFAULT_ENV_PATH = PROJECT_ROOT / ".env"
DEFAULT_AUDIT_PATH = PROJECT_ROOT / "data" / "audit.jsonl"
SANDBOX_BASE_URL = "https://api-m.sandbox.paypal.com"
DEFAULT_LLM_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"
DEFAULT_LLM_MODEL = "gemini-3.5-flash-lite"


class ConfigurationError(ValueError):
    """Configuration invalide ou dangereuse."""


def load_env_file(path: str | Path = DEFAULT_ENV_PATH) -> None:
    """Charge des paires KEY=VALUE sans écraser l'environnement existant."""

    env_path = Path(path)
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        if key.startswith("export "):
            key = key.removeprefix("export ").strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass(frozen=True)
class Settings:
    """Paramètres runtime, tous optionnels sauf la contrainte sandbox."""

    paypal_client_id: str = ""
    paypal_client_secret: str = ""
    paypal_base_url: str = SANDBOX_BASE_URL
    llm_base_url: str = DEFAULT_LLM_BASE_URL
    llm_api_key: str = ""
    llm_model: str = DEFAULT_LLM_MODEL
    audit_path: Path = DEFAULT_AUDIT_PATH

    def __post_init__(self) -> None:
        if "sandbox" not in self.paypal_base_url.lower():
            raise ConfigurationError(
                "PayGuard refuse toute URL PayPal hors sandbox : "
                f"{self.paypal_base_url!r}."
            )
        if bool(self.paypal_client_id) != bool(self.paypal_client_secret):
            raise ConfigurationError(
                "PAYPAL_CLIENT_ID et PAYPAL_CLIENT_SECRET doivent être "
                "renseignés ensemble."
            )

    @property
    def paypal_configured(self) -> bool:
        return bool(self.paypal_client_id and self.paypal_client_secret)

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_api_key and self.llm_model)


def load_settings(env_path: str | Path = DEFAULT_ENV_PATH) -> Settings:
    """Charge `.env` puis construit les paramètres validés."""

    load_env_file(env_path)
    audit_path = os.environ.get("PAYGUARD_AUDIT_PATH", "").strip()
    audit_file = Path(audit_path) if audit_path else DEFAULT_AUDIT_PATH
    if not audit_file.is_absolute():
        audit_file = PROJECT_ROOT / audit_file

    return Settings(
        paypal_client_id=os.environ.get("PAYPAL_CLIENT_ID", "").strip(),
        paypal_client_secret=os.environ.get("PAYPAL_CLIENT_SECRET", "").strip(),
        paypal_base_url=os.environ.get("PAYPAL_BASE_URL", SANDBOX_BASE_URL).strip(),
        llm_base_url=os.environ.get("LLM_BASE_URL", DEFAULT_LLM_BASE_URL).strip(),
        llm_api_key=os.environ.get("LLM_API_KEY", "").strip(),
        llm_model=os.environ.get("LLM_MODEL", DEFAULT_LLM_MODEL).strip(),
        audit_path=audit_file,
    )
