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

# Ícones por severidade numérica do Zabbix (EVENT.NSEVERITY)
_NSEVERITY: dict[str, str] = {
    "5": "💀 Disaster",
    "4": "🔴 High",
    "3": "🟠 Average",
    "2": "🟡 Warning",
    "1": "🔵 Information",
    "0": "⚪ Not classified",
}

_DIVIDER = "━━━━━━━━━━━━━━━━━━━━"


def _format_message(alert: ZabbixAlertRequest) -> str:
    is_recovery = (alert.event_value or "").strip() == "0"
    is_update   = (alert.event_update_status or "").strip() == "1"

    sev_label = _NSEVERITY.get(
        (alert.event_nseverity or "").strip(),
        f"⚠️ {alert.severity}" if alert.severity else "⚠️ Unknown",
    )

    # ── Header ────────────────────────────────────────────────────────────────
    if is_recovery:
        header = f"🟢 *RESOLVIDO*"
        title  = "PROBLEMA RESOLVIDO"
    elif is_update:
        header = f"🔄 *ATUALIZAÇÃO* — {sev_label}"
        title  = "ATUALIZAÇÃO DE PROBLEMA"
    else:
        header = f"{sev_label} — *PROBLEMA*"
        title  = "ALERTA ZABBIX"

    lines: list[str] = [header, _DIVIDER]

    # ── Details ───────────────────────────────────────────────────────────────
    if alert.trigger_name:
        lines.append(f"📌 *Problema:* {alert.trigger_name}")

    if alert.host:
        lines.append(f"🏷 *Host:* {alert.host}")

    lines.append(f"⚠️ *Severidade:* {'RESOLVIDO' if is_recovery else sev_label}")

    if alert.event_date and alert.event_time:
        lines.append(f"🕒 *Horário:* {alert.event_date} {alert.event_time}")
    else:
        lines.append(f"🕒 *Horário:* {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

    if alert.event_id:
        lines.append(f"🆔 *Event ID:* {alert.event_id}")

    # ── Link Zabbix ───────────────────────────────────────────────────────────
    if alert.zabbix_url and alert.event_id:
        base = alert.zabbix_url.rstrip("/")
        link = f"{base}/zabbix.php?action=problem.view&eventid={alert.event_id}"
        lines.append(f"\n🔗 *Abrir no Zabbix:*\n{link}")

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
    to                  → {ALERT.SENDTO}
    subject             → {ALERT.SUBJECT}
    body                → {ALERT.MESSAGE}
    severity            → {EVENT.SEVERITY}
    event_nseverity     → {EVENT.NSEVERITY}
    status              → {EVENT.STATUS}
    event_value         → {EVENT.VALUE}
    event_update_status → {EVENT.UPDATE.STATUS}
    event_id            → {EVENT.ID}
    trigger_name        → {TRIGGER.NAME}
    host                → {HOST.NAME}
    event_date          → {EVENT.DATE}
    event_time          → {EVENT.TIME}
    zabbix_url          → http://seu-zabbix.local/
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
