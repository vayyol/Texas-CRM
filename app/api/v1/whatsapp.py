"""Endpoints da central WhatsApp do TexasCRM."""
from __future__ import annotations

import hmac
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.dependencies import get_current_active_user
from app.database import get_db
from app.models.whatsapp import (
    WhatsAppConsent,
    WhatsAppConversation,
    WhatsAppMessage,
    WhatsAppSession,
)
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


class SendMessageRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


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
        consent = WhatsAppConsent(
            user_id=current_user.id,
            terms_version=settings.WHATSAPP_TERMS_VERSION,
            accepted_at=datetime.now(timezone.utc),
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent", "")[:500] or None,
        )
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

    session = WhatsAppSession(
        user_id=current_user.id,
        session_name=session_name,
        status=remote.get("status", "STOPPED"),
    )
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
        # Recupera sessões que ficaram salvas no banco, mas foram removidas do WAHA.
        await waha_client.ensure_session(session.session_name)
        await waha_client.update_session_webhooks(session.session_name)
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


@router.post("/webhook", summary="Receber eventos do WAHA")
async def receive_waha_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    webhook_key: str | None = Header(default=None, alias="X-TexasCRM-Webhook-Key"),
):
    expected = settings.WAHA_API_KEY.get_secret_value()
    if not expected or not webhook_key or not hmac.compare_digest(webhook_key, expected):
        raise HTTPException(status_code=401, detail="Webhook não autorizado.")

    event_data = await request.json()
    if not isinstance(event_data, dict):
        return {"received": True, "ignored": True}

    session_name = event_data.get("session")
    event = event_data.get("event")
    if not isinstance(session_name, str):
        return {"received": True, "ignored": True}

    result = await db.execute(select(WhatsAppSession).where(WhatsAppSession.session_name == session_name))
    session = result.scalar_one_or_none()
    if session is None:
        return {"received": True, "ignored": True}

    payload = event_data.get("payload") or {}
    if event == "session.status":
        new_status = payload.get("status") if isinstance(payload, dict) else None
        if isinstance(new_status, str):
            session.status = new_status
            if new_status == "WORKING":
                session.connected_at = datetime.now(timezone.utc)
                me = event_data.get("me") or {}
                jid = me.get("id") if isinstance(me, dict) else None
                if isinstance(jid, str):
                    session.phone_number = jid.split("@", 1)[0]
            elif new_status in {"STOPPED", "FAILED"}:
                session.connected_at = None
        return {"received": True, "event": event}

    if event != "message" or not isinstance(payload, dict):
        return {"received": True, "ignored": True}

    message_id = payload.get("id")
    body = payload.get("body")
    from_me = bool(payload.get("fromMe"))
    chat_id = payload.get("to") if from_me else payload.get("from")
    if not isinstance(message_id, str) or not isinstance(body, str) or not body.strip():
        return {"received": True, "ignored": True}
    if not isinstance(chat_id, str) or not chat_id:
        return {"received": True, "ignored": True}

    duplicate = await db.execute(select(WhatsAppMessage.id).where(WhatsAppMessage.waha_message_id == message_id))
    if duplicate.scalar_one_or_none():
        return {"received": True, "duplicate": True}

    conversation_result = await db.execute(
        select(WhatsAppConversation).where(
            WhatsAppConversation.session_id == session.id,
            WhatsAppConversation.chat_id == chat_id,
        )
    )
    conversation = conversation_result.scalar_one_or_none()
    if conversation is None:
        phone = chat_id.split("@", 1)[0] if chat_id.endswith("@c.us") else None
        raw_data = payload.get("_data") or {}
        display_name = None
        if isinstance(raw_data, dict):
            display_name = raw_data.get("notifyName") or raw_data.get("pushName")
        conversation = WhatsAppConversation(
            user_id=session.user_id,
            session_id=session.id,
            chat_id=chat_id,
            contact_name=display_name or phone or chat_id,
            contact_phone=phone,
        )
        db.add(conversation)
        await db.flush()

    timestamp = payload.get("timestamp")
    sent_at = datetime.fromtimestamp(timestamp, tz=timezone.utc) if isinstance(timestamp, (int, float)) else datetime.now(timezone.utc)
    conversation.last_message_at = sent_at
    conversation.last_message_preview = body.strip()[:500]
    if not from_me:
        conversation.unread_count += 1

    db.add(
        WhatsAppMessage(
            user_id=session.user_id,
            conversation_id=conversation.id,
            waha_message_id=message_id,
            direction="out" if from_me else "in",
            body=body.strip(),
            message_type="text",
            status="sent" if from_me else "received",
            sent_at=sent_at,
        )
    )
    return {"received": True, "event": "message"}


@router.get("/conversations", summary="Listar conversas WhatsApp")
async def list_whatsapp_conversations(
    current_user=Depends(get_current_active_user), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(WhatsAppConversation)
        .where(WhatsAppConversation.user_id == current_user.id)
        .order_by(WhatsAppConversation.last_message_at.desc().nullslast())
    )
    conversations = result.scalars().all()
    return [
        {
            "id": str(item.id),
            "chat_id": item.chat_id,
            "contact_name": item.contact_name,
            "contact_phone": item.contact_phone,
            "last_message_at": item.last_message_at,
            "last_message_preview": item.last_message_preview,
            "unread_count": item.unread_count,
        }
        for item in conversations
    ]


@router.get("/conversations/{conversation_id}/messages", summary="Listar mensagens de uma conversa")
async def list_whatsapp_messages(
    conversation_id: uuid.UUID,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    conversation_result = await db.execute(
        select(WhatsAppConversation).where(
            WhatsAppConversation.id == conversation_id,
            WhatsAppConversation.user_id == current_user.id,
        )
    )
    conversation = conversation_result.scalar_one_or_none()
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversa não encontrada.")
    conversation.unread_count = 0
    messages_result = await db.execute(
        select(WhatsAppMessage)
        .where(
            WhatsAppMessage.conversation_id == conversation.id,
            WhatsAppMessage.user_id == current_user.id,
        )
        .order_by(WhatsAppMessage.sent_at.asc().nullsfirst(), WhatsAppMessage.created_at.asc())
        .limit(200)
    )
    return [
        {
            "id": str(item.id),
            "direction": item.direction,
            "body": item.body,
            "status": item.status,
            "sent_at": item.sent_at,
        }
        for item in messages_result.scalars().all()
    ]


@router.post("/conversations/{conversation_id}/messages", status_code=status.HTTP_201_CREATED, summary="Enviar mensagem de texto")
async def send_whatsapp_message(
    conversation_id: uuid.UUID,
    body: SendMessageRequest,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    conversation_result = await db.execute(
        select(WhatsAppConversation).where(
            WhatsAppConversation.id == conversation_id,
            WhatsAppConversation.user_id == current_user.id,
        )
    )
    conversation = conversation_result.scalar_one_or_none()
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversa não encontrada.")

    session_result = await db.execute(
        select(WhatsAppSession).where(
            WhatsAppSession.id == conversation.session_id,
            WhatsAppSession.user_id == current_user.id,
        )
    )
    session = session_result.scalar_one_or_none()
    if session is None or session.status != "WORKING":
        raise HTTPException(status_code=409, detail="Conecte o WhatsApp antes de enviar mensagens.")

    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="A mensagem não pode estar vazia.")
    try:
        remote = await waha_client.send_text(session.session_name, conversation.chat_id, text)
    except waha_client.WahaNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except waha_client.WahaAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    message_id = remote.get("id") if isinstance(remote, dict) else None
    timestamp = remote.get("timestamp") if isinstance(remote, dict) else None
    sent_at = datetime.fromtimestamp(timestamp, tz=timezone.utc) if isinstance(timestamp, (int, float)) else datetime.now(timezone.utc)
    message = WhatsAppMessage(
        user_id=current_user.id,
        conversation_id=conversation.id,
        waha_message_id=message_id if isinstance(message_id, str) else None,
        direction="out",
        body=text,
        message_type="text",
        status="sent",
        sent_at=sent_at,
    )
    db.add(message)
    conversation.last_message_at = sent_at
    conversation.last_message_preview = text[:500]
    await db.flush()
    return {"id": str(message.id), "status": "sent", "sent_at": sent_at}
