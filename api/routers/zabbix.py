from fastapi import APIRouter, Depends, HTTPException, status
import httpx
import logging
from datetime import datetime

from api.auth import require_api_key
from api.models.schemas import ZabbixAlertRequest, MessageResponse
from api.services.whatsapp_client import whatsapp_client

logger = logging.getLogger("api.zabbix")
router = APIRouter(prefix="/zabbix", tags=["Zabbix"])

# ─── Formatting helpers ───────────────────────────────────────────────────────

_SEVERITY_ICON: dict[str, str] = {
    "not classified": "⚪",
    "information":    "🔵",
    "warning":        "🟡",
    "average":        "🟠",
    "high":           "🔴",
    "disaster":       "🚨",
}

_STATUS_ICON: dict[str, str] = {
    "problem":      "🚨",
    "resolved":     "✅",
    "acknowledged": "👁️",
}

_DIVIDER = "━━━━━━━━━━━━━━━━━━━━"


def _format_message(alert: ZabbixAlertRequest) -> str:
    severity_key = (alert.severity or "").strip().lower()
    status_key   = (alert.status or "").strip().lower()

    sev_icon    = _SEVERITY_ICON.get(severity_key, "⚠️")
    status_icon = _STATUS_ICON.get(status_key, "⚠️")

    lines: list[str] = []

    # ── Header ────────────────────────────────────────────────────────────────
    if status_key == "resolved":
        lines.append(f"✅ *RESOLVIDO* {sev_icon}")
    elif status_key == "problem":
        sev_label = (alert.severity or "ALERTA").upper()
        lines.append(f"🚨 *PROBLEMA — {sev_label}* {sev_icon}")
    else:
        lines.append(f"{status_icon} *{alert.subject}*")

    lines.append(_DIVIDER)

    # ── Details ───────────────────────────────────────────────────────────────
    if alert.trigger_name:
        lines.append(f"📋 *Trigger:* {alert.trigger_name}")

    if alert.host:
        lines.append(f"🖥️ *Host:* {alert.host}")

    if alert.event_date and alert.event_time:
        lines.append(f"🕐 *Horário:* {alert.event_date} {alert.event_time}")
    else:
        lines.append(f"🕐 *Horário:* {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

    lines.append(_DIVIDER)

    # ── Body ──────────────────────────────────────────────────────────────────
    if alert.body:
        lines.append("ℹ️ *Detalhes:*")
        lines.append(alert.body)
        lines.append(_DIVIDER)

    # ── Footer ────────────────────────────────────────────────────────────────
    if alert.event_id:
        lines.append(f"🆔 Event ID: {alert.event_id}")

    return "\n".join(lines)


# ─── Route ───────────────────────────────────────────────────────────────────

@router.post(
    "/alert",
    response_model=MessageResponse,
    summary="Receber alerta do Zabbix e enviar via WhatsApp",
)
async def receive_zabbix_alert(
    alert: ZabbixAlertRequest,
    _: str = Depends(require_api_key),
):
    """
    Endpoint para configurar como **Webhook** no Zabbix.

    Parâmetros sugeridos no Zabbix:
    ```
    to           → {ALERT.SENDTO}
    subject      → {ALERT.SUBJECT}
    body         → {ALERT.MESSAGE}
    severity     → {EVENT.SEVERITY}
    status       → {EVENT.STATUS}
    event_id     → {EVENT.ID}
    trigger_name → {TRIGGER.NAME}
    host         → {HOST.NAME}
    event_date   → {EVENT.DATE}
    event_time   → {EVENT.TIME}
    ```
    """
    message = _format_message(alert)

    try:
        if alert.is_group:
            result = await whatsapp_client.send_group_message(alert.to, message)
        else:
            result = await whatsapp_client.send_message(alert.to, message)

        logger.info(
            "Zabbix alert sent → %s  event_id=%s  status=%s",
            alert.to,
            alert.event_id,
            alert.status,
        )
        return MessageResponse(success=True, message_id=result.get("messageId"))

    except httpx.HTTPStatusError as exc:
        try:
            detail = exc.response.json().get("error", str(exc))
        except Exception:
            detail = str(exc)
        logger.error("Failed to send Zabbix alert: %s", detail)
        raise HTTPException(status_code=exc.response.status_code, detail=detail)

    except httpx.RequestError as exc:
        logger.error("WhatsApp service unavailable: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Serviço WhatsApp indisponível",
        )
