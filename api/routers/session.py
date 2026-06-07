from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
import base64
import httpx
import logging

from api.auth import require_api_key
from api.services.whatsapp_client import whatsapp_client, WhatsAppServiceError

logger = logging.getLogger("api.session")
router = APIRouter(prefix="/session", tags=["Sessão"])


@router.get("/status", summary="Status da conexão WhatsApp")
async def get_status(_: str = Depends(require_api_key)):
    """Retorna o status atual da conexão WhatsApp."""
    try:
        return await whatsapp_client.get_status()
    except httpx.RequestError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Serviço WhatsApp indisponível",
        )
    except WhatsAppServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )


@router.post("/pair-code", summary="Gerar código de pareamento (sem QR)")
async def get_pair_code(number: str | None = None, _: str = Depends(require_api_key)):
    """
    Gera código de pareamento para conectar sem QR.
    Envie o número com DDI (ex: 5511999999999).
    """
    try:
        return await whatsapp_client.get_pairing_code(number)
    except httpx.HTTPStatusError as exc:
        try:
            detail = exc.response.json().get("error", str(exc))
        except Exception:
            detail = str(exc)
        raise HTTPException(status_code=exc.response.status_code, detail=detail)
    except httpx.RequestError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Serviço WhatsApp indisponível",
        )
    except WhatsAppServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )


@router.get("/qr", summary="QR Code para autenticação (JSON)")
async def get_qr(_: str = Depends(require_api_key)):
    """
    Retorna o QR Code em base64 (data URL).
    Escaneie com o WhatsApp do celular para autenticar.
    """
    try:
        return await whatsapp_client.get_qr()
    except httpx.HTTPStatusError as exc:
        try:
            detail = exc.response.json().get("error", str(exc))
        except Exception:
            detail = str(exc)
        raise HTTPException(status_code=exc.response.status_code, detail=detail)
    except httpx.RequestError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Serviço WhatsApp indisponível",
        )
    except WhatsAppServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )


@router.get(
    "/qr/image",
    response_class=Response,
    summary="QR Code como imagem PNG",
    responses={200: {"content": {"image/png": {}}}},
)
async def get_qr_image(_: str = Depends(require_api_key)):
    """Retorna o QR Code diretamente como imagem PNG para exibir no browser."""
    try:
        result = await whatsapp_client.get_qr()
    except httpx.RequestError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Serviço WhatsApp indisponível",
        )
    except WhatsAppServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )

    if "qr" not in result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.get("message", "QR Code não disponível"),
        )

    qr_data = result["qr"]
    if "," in qr_data:
        qr_data = qr_data.split(",", 1)[1]

    image_bytes = base64.b64decode(qr_data)
    return Response(content=image_bytes, media_type="image/png")


@router.get("/chats", summary="Listar chats (útil para obter IDs de grupos)")
async def get_chats(_: str = Depends(require_api_key)):
    """Lista todos os chats abertos — use para descobrir o ID de grupos."""
    try:
        return await whatsapp_client.get_chats()
    except httpx.HTTPStatusError as exc:
        try:
            detail = exc.response.json().get("error", str(exc))
        except Exception:
            detail = str(exc)
        raise HTTPException(status_code=exc.response.status_code, detail=detail)
    except httpx.RequestError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Serviço WhatsApp indisponível",
        )
