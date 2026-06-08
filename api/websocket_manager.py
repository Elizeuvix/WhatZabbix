"""
WebSocket manager — broadcast de alertas Zabbix para clientes conectados.
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Any
from fastapi import WebSocket

logger = logging.getLogger("api.websocket")

# Histórico em memória (últimas 200 mensagens)
_MAX_HISTORY = 200
_alert_history: list[dict] = []


class WebSocketManager:
    def __init__(self) -> None:
        self._clients: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._clients.append(ws)
        logger.info("[WS] Cliente conectado. Total: %d", len(self._clients))
        # Envia histórico para o novo cliente
        if _alert_history:
            await ws.send_text(json.dumps({
                "type": "history",
                "alerts": _alert_history,
            }))

    def disconnect(self, ws: WebSocket) -> None:
        self._clients = [c for c in self._clients if c is not ws]
        logger.info("[WS] Cliente desconectado. Total: %d", len(self._clients))

    async def broadcast(self, payload: dict) -> None:
        """Armazena no histórico e envia para todos os clientes conectados."""
        _alert_history.append(payload)
        if len(_alert_history) > _MAX_HISTORY:
            _alert_history.pop(0)

        message = json.dumps({"type": "alert", "alert": payload})
        dead: list[WebSocket] = []
        for ws in self._clients:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    def get_history(self) -> list[dict]:
        return list(_alert_history)


ws_manager = WebSocketManager()
