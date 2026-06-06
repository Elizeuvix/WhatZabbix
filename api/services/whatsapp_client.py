import httpx
import logging
from api.config import settings

logger = logging.getLogger("api.whatsapp_client")


class WhatsAppServiceError(Exception):
    """Raised when the WhatsApp internal service returns an error."""


class WhatsAppClient:
    """Async HTTP client for the internal whatsapp-web.js service."""

    def __init__(self) -> None:
        self._base = settings.whatsapp_service_url.rstrip("/")
        self._timeout = settings.whatsapp_service_timeout

    # ── Internal ──────────────────────────────────────────────────────────────

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._base,
            timeout=self._timeout,
        )

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
        return await self._get("/status")

    async def get_qr(self) -> dict:
        return await self._get("/qr")

    async def get_chats(self) -> list:
        data = await self._get("/chats")
        return data if isinstance(data, list) else []

    async def send_message(self, number: str, message: str) -> dict:
        return await self._post("/send", {"number": number, "message": message})

    async def send_group_message(self, group_id: str, message: str) -> dict:
        return await self._post("/send-group", {"groupId": group_id, "message": message})


# Singleton
whatsapp_client = WhatsAppClient()
