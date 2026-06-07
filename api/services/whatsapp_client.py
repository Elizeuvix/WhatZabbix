import httpx
import logging
from api.config import settings

logger = logging.getLogger("api.whatsapp_client")


class WhatsAppServiceError(Exception):
    """Raised when the WhatsApp internal service returns an error."""


class WhatsAppClient:
    """Async client that routes calls to the configured WhatsApp provider."""

    def __init__(self) -> None:
        self._provider = settings.whatsapp_provider.strip().lower()
        self._base = settings.whatsapp_service_url.rstrip("/")
        self._timeout = settings.whatsapp_service_timeout

    # ── Provider helpers ──────────────────────────────────────────────────────

    def _is_meta(self) -> bool:
        return self._provider == "meta"

    def _normalize_phone(self, number: str) -> str:
        return "".join(ch for ch in number if ch.isdigit())

    def _meta_headers(self) -> dict:
        if not settings.meta_access_token:
            raise WhatsAppServiceError("META_ACCESS_TOKEN não configurado")
        return {
            "Authorization": f"Bearer {settings.meta_access_token}",
            "Content-Type": "application/json",
        }

    def _meta_phone_number_id(self) -> str:
        if not settings.meta_phone_number_id:
            raise WhatsAppServiceError("META_PHONE_NUMBER_ID não configurado")
        return settings.meta_phone_number_id

    def _meta_client(self) -> httpx.AsyncClient:
        base = f"{settings.meta_graph_base_url.rstrip('/')}/{settings.meta_api_version}"
        return httpx.AsyncClient(base_url=base, timeout=self._timeout)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._base,
            timeout=self._timeout,
        )

    async def _meta_post(self, path: str, payload: dict) -> dict:
        async with self._meta_client() as c:
            r = await c.post(path, json=payload, headers=self._meta_headers())
            r.raise_for_status()
            return r.json()

    async def _get(self, path: str) -> dict:
        async with self._client() as c:
            r = await c.get(path)
            r.raise_for_status()
            return r.json()

    async def _post(self, path: str, payload: dict) -> dict:
        async with self._client() as c:
            r = await c.post(path, json=payload)
            r.raise_for_status()
            return r.json()

    # ── Public API ────────────────────────────────────────────────────────────

    async def get_status(self) -> dict:
        if self._is_meta():
            ready = bool(settings.meta_access_token and settings.meta_phone_number_id)
            return {
                "status": "ready" if ready else "disconnected",
                "provider": "meta",
                "message": "WhatsApp Cloud API não usa sessão local/QR",
            }
        return await self._get("/status")

    async def get_qr(self) -> dict:
        if self._is_meta():
            return {
                "status": "ready",
                "provider": "meta",
                "message": "QR não se aplica ao provedor oficial Meta",
            }
        return await self._get("/qr")

    async def get_pairing_code(self, number: str | None = None) -> dict:
        if self._is_meta():
            return {
                "status": "ready",
                "provider": "meta",
                "message": "Pareamento por código não se aplica ao provedor oficial Meta",
            }
        payload = {"number": number} if number else {}
        return await self._post("/pair-code", payload)

    async def get_chats(self) -> list:
        if self._is_meta():
            return []
        data = await self._get("/chats")
        return data if isinstance(data, list) else []

    async def send_message(self, number: str, message: str) -> dict:
        if self._is_meta():
            phone_number_id = self._meta_phone_number_id()
            payload = {
                "messaging_product": "whatsapp",
                "to": self._normalize_phone(number),
                "type": "text",
                "text": {
                    "preview_url": False,
                    "body": message,
                },
            }
            data = await self._meta_post(f"/{phone_number_id}/messages", payload)
            msg_id = None
            if isinstance(data, dict):
                msgs = data.get("messages") or []
                if msgs and isinstance(msgs[0], dict):
                    msg_id = msgs[0].get("id")
            return {"success": True, "messageId": msg_id}
        return await self._post("/send", {"number": number, "message": message})

    async def send_group_message(self, group_id: str, message: str) -> dict:
        if self._is_meta():
            raise WhatsAppServiceError(
                "Envio para grupos não é suportado pelo WhatsApp Cloud API"
            )
        return await self._post("/send-group", {"groupId": group_id, "message": message})


# Singleton
whatsapp_client = WhatsAppClient()
