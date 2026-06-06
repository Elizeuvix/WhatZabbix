from fastapi import APIRouter, Depends, HTTPException, status
import httpx
import logging

from api.auth import require_api_key
from api.models.schemas import SendMessageRequest, SendGroupMessageRequest, MessageResponse
from api.services.whatsapp_client import whatsapp_client

logger = logging.getLogger("api.messages")
router = APIRouter(prefix="/messages", tags=["Mensagens"])


def _handle_http_error(exc: httpx.HTTPStatusError) -> HTTPException:
    try:
        detail = exc.response.json().get("error", str(exc))
    except Exception:
        detail = str(exc)
    return HTTPException(status_code=exc.response.status_code, detail=detail)


@router.post(
    "/send",
    response_model=MessageResponse,
    summary="Enviar mensagem para número",
)
async def send_message(
    body: SendMessageRequest,
    _: str = Depends(require_api_key),
):
    """Envia uma mensagem de texto para um número WhatsApp."""
    try:
        result = await whatsapp_client.send_message(body.number, body.message)
        return MessageResponse(success=True, message_id=result.get("messageId"))
    except httpx.HTTPStatusError as exc:
        raise _handle_http_error(exc)
    except httpx.RequestError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Serviço WhatsApp indisponível",
        )


@router.post(
    "/send-group",
    response_model=MessageResponse,
    summary="Enviar mensagem para grupo",
)
async def send_group_message(
    body: SendGroupMessageRequest,
    _: str = Depends(require_api_key),
):
    """Envia uma mensagem de texto para um grupo WhatsApp."""
    try:
        result = await whatsapp_client.send_group_message(body.group_id, body.message)
        return MessageResponse(success=True, message_id=result.get("messageId"))
    except httpx.HTTPStatusError as exc:
        raise _handle_http_error(exc)
    except httpx.RequestError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Serviço WhatsApp indisponível",
        )
