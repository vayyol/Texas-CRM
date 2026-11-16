"""Endpoints iniciais e autenticados da central WhatsApp."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.dependencies import get_current_active_user
from app.database import get_db
from app.models.whatsapp import WhatsAppConsent, WhatsAppSession
from app.services import waha_client

router = APIRouter()

TERMS_TEXT = (
    "O TexasCRM utiliza o WAHA, uma tecnologia de terceiros, não oficial e não pertencente ao WhatsApp/Meta, "
    "para conectar sua conta por meio de uma sessão semelhante ao WhatsApp Web. O uso pode estar sujeito a "
    "desconexões, instabilidade, perda da sessão e medidas de restrição ou bloqueio aplicadas pelo WhatsApp. "
    "Você declara que tem autorização para conectar o número informado, que utilizará o recurso de forma lícita "
    "e que é responsável pelo conteúdo e pelas mensagens enviadas. Não há garantia de disponibilidade contínua. "
    "O tratamento de dados pessoais e mensagens deve respeitar a legislação aplicável, inclusive a LGPD. "
    "Você pode desconectar sua sessão a qualquer momento."
)


class ConsentRequest(BaseModel):
    accepted: bool
    terms_version: str = Field(min_length=1, max_length=30)


@router.get("/terms", summary="Consultar termo de uso do WhatsApp")
async def get_terms():
    return {"version": settings.WHATSAPP_TERMS_VERSION, "text": TERMS_TEXT}


@router.get("/status", summary="Consultar configuração e aceite do WhatsApp")
async def get_whatsapp_status(
    current_user=Depends(get_current_active_user), db: AsyncSession = Depends(get_db)
):
    consent_result = await db.execute(select(WhatsAppConsent).where(WhatsAppConsent.user_id == current_user.id))
    consent = consent_result.scalar_one_or_none()
    session_result = await db.execute(select(WhatsAppSession).where(WhatsAppSession.user_id == current_user.id))
    session = session_result.scalar_one_or_none()
    return {
        "integration_configured": bool(settings.WAHA_BASE_URL and settings.WAHA_API_KEY.get_secret_value()),
        "terms_version": settings.WHATSAPP_TERMS_VERSION,
        "terms_accepted": bool(consent and consent.terms_version == settings.WHATSAPP_TERMS_VERSION),
        "accepted_at": consent.accepted_at if consent else None,
        "session": {"name": session.session_name, "status": session.status, "phone_number": session.phone_number} if session else None,
    }


@router.post("/consent", status_code=status.HTTP_200_OK, summary="Registrar aceite do termo WhatsApp")
async def accept_whatsapp_terms(
    body: ConsentRequest,
    request: Request,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    if not body.accepted:
        raise HTTPException(status_code=400, detail="É necessário aceitar o termo para continuar.")
    if body.terms_version != settings.WHATSAPP_TERMS_VERSION:
        raise HTTPException(status_code=409, detail="O termo foi atualizado. Consulte a versão atual antes de aceitar.")

    result = await db.execute(select(WhatsAppConsent).where(WhatsAppConsent.user_id == current_user.id))
    consent = result.scalar_one_or_none()
    if consent is None:
        consent = WhatsAppConsent(user_id=current_user.id, terms_version=settings.WHATSAPP_TERMS_VERSION,
                                  accepted_at=datetime.now(timezone.utc),
                                  ip_address=request.client.host if request.client else None,
                                  user_agent=request.headers.get("user-agent", "")[:500] or None)
        db.add(consent)
    else:
        consent.terms_version = settings.WHATSAPP_TERMS_VERSION
        consent.accepted_at = datetime.now(timezone.utc)
        consent.ip_address = request.client.host if request.client else None
        consent.user_agent = request.headers.get("user-agent", "")[:500] or None
    await db.flush()
    return {"accepted": True, "terms_version": settings.WHATSAPP_TERMS_VERSION, "accepted_at": consent.accepted_at}


@router.post("/session", status_code=status.HTTP_201_CREATED, summary="Criar sessão WAHA do usuário")
async def create_whatsapp_session(
    current_user=Depends(get_current_active_user), db: AsyncSession = Depends(get_db)
):
    consent_result = await db.execute(select(WhatsAppConsent).where(WhatsAppConsent.user_id == current_user.id))
    consent = consent_result.scalar_one_or_none()
    if not consent or consent.terms_version != settings.WHATSAPP_TERMS_VERSION:
        raise HTTPException(status_code=403, detail="Aceite o termo atual antes de criar uma sessão.")

    existing_result = await db.execute(select(WhatsAppSession).where(WhatsAppSession.user_id == current_user.id))
    existing = existing_result.scalar_one_or_none()
    if existing:
        return {"name": existing.session_name, "status": existing.status, "created": False}

    session_name = f"tc_{uuid.uuid4().hex}"
    try:
        remote = await waha_client.create_session(session_name)
    except waha_client.WahaNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except waha_client.WahaAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    session = WhatsAppSession(user_id=current_user.id, session_name=session_name,
                              status=remote.get("status", "STOPPED"))
    db.add(session)
    await db.flush()
    return {"name": session.session_name, "status": session.status, "created": True}


@router.post("/session/start", summary="Iniciar sessão WhatsApp")
async def start_whatsapp_session(
    current_user=Depends(get_current_active_user), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(WhatsAppSession).where(WhatsAppSession.user_id == current_user.id))
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Nenhuma sessão WhatsApp foi criada.")
    try:
        remote = await waha_client.start_session(session.session_name)
    except waha_client.WahaNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except waha_client.WahaAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    session.status = remote.get("status", "STARTING") if isinstance(remote, dict) else "STARTING"
    await db.flush()
    return {"name": session.session_name, "status": session.status}


@router.get("/session/qr", summary="Obter QR Code da sessão WhatsApp")
async def get_whatsapp_qr(
    current_user=Depends(get_current_active_user), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(WhatsAppSession).where(WhatsAppSession.user_id == current_user.id))
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Nenhuma sessão WhatsApp foi criada.")
    try:
        qr = await waha_client.get_qr(session.session_name)
    except waha_client.WahaNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except waha_client.WahaAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if not isinstance(qr, dict) or not qr.get("data"):
        raise HTTPException(status_code=409, detail="QR Code ainda não está disponível. Tente novamente em alguns segundos.")
    return {"mimetype": qr.get("mimetype", "image/png"), "data": qr["data"]}
