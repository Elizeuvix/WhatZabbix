from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # ── API Keys ──────────────────────────────────────────────────────────────
    # Comma-separated. Generate with: python -c "import secrets; print(secrets.token_hex(32))"
    api_keys: str = ""

    # ── Debug ────────────────────────────────────────────────────────────────
    # Enables /docs and /redoc — disable in production
    debug: bool = False

    # ── CORS ─────────────────────────────────────────────────────────────────
    # Comma-separated origins. Use * for all (not recommended in production)
    allowed_origins: str = "*"

    # ── WhatsApp provider ─────────────────────────────────────────────────────
    # internal -> local Node service (legacy)
    # meta     -> official WhatsApp Cloud API
    whatsapp_provider: str = "internal"

    # ── WhatsApp internal service (legacy) ───────────────────────────────────
    whatsapp_service_url: str = "http://localhost:3000"
    whatsapp_service_timeout: int = 30  # seconds

    # ── WhatsApp Cloud API (official) ────────────────────────────────────────
    meta_api_version: str = "v20.0"
    meta_graph_base_url: str = "https://graph.facebook.com"
    meta_access_token: str = ""
    meta_phone_number_id: str = ""

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }

    @property
    def api_keys_list(self) -> List[str]:
        return [k.strip() for k in self.api_keys.split(",") if k.strip()]

    @property
    def allowed_origins_list(self) -> List[str]:
        if self.allowed_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


settings = Settings()
