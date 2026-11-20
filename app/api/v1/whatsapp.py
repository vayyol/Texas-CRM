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
from app.services import uazapi_client, waha_client
from app.services.whatsapp_tokens import decrypt_token, encrypt_token

router = APIRouter()

TERMS_TEXT = (
    "O TexasCRM utiliza uma integração de terceiros, não oficial e não pertencente ao WhatsApp/Meta, "
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
    # Consulta o estado real no WAHA: depender apenas do webhook pode deixar
    # o banco preso em STARTING e impedir o frontend de pedir o QR Code.
    if session is not None and session.provider == "waha":
        try:
            remote = await waha_client.get_session(session.session_name)
            if isinstance(remote, dict) and isinstance(remote.get("status"), str):
                session.status = remote["status"]
                me = remote.get("me")
                if isinstance(me, dict) and isinstance(me.get("id"), str):
                    session.phone_number = me["id"].split("@", 1)[0]
                await db.flush()
        except (waha_client.WahaAPIError, waha_client.WahaNotConfiguredError):
            # Mantém o último estado conhecido se a consulta remota falhar.
            pass
    if session is not None and session.provider == "uazapi" and session.provider_token_encrypted:
        try:
            remote = await uazapi_client.status(decrypt_token(session.provider_token_encrypted))
            remote_status = remote.get("status")
            if isinstance(remote_status, str):
                session.status = {"connected": "WORKING", "connecting": "SCAN_QR_CODE", "disconnected": "STOPPED", "hibernated": "STOPPED"}.get(remote_status.lower(), remote_status.upper())
            owner = remote.get("owner") or remote.get("phone")
            if isinstance(owner, str):
                session.phone_number = owner.split("@", 1)[0]
            await db.flush()
        except (uazapi_client.UazapiAPIError, RuntimeError):
            pass
    return {
        "integration_configured": (settings.UAZAPI_ADMIN_TOKEN.get_secret_value() != "" if settings.WHATSAPP_PROVIDER == "uazapi" else bool(settings.WAHA_BASE_URL and settings.WAHA_API_KEY.get_secret_value())),
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
    provider = settings.WHATSAPP_PROVIDER.strip().lower()
    try:
        if provider == "uazapi":
            remote = await uazapi_client.create_instance(session_name)
            instance = remote.get("instance") if isinstance(remote.get("instance"), dict) else remote
            token = remote.get("token") or remote.get("apikey") or instance.get("token") or instance.get("apikey")
            if not isinstance(token, str) or not token:
                raise HTTPException(status_code=502, detail="UazapiGO não retornou o token da instância.")
            session = WhatsAppSession(
                user_id=current_user.id, session_name=session_name, provider="uazapi",
                provider_token_encrypted=encrypt_token(token),
                provider_instance_id=str(instance.get("id") or remote.get("id") or ""),
                status=str(instance.get("status") or "DISCONNECTED").upper(),
            )
        else:
            remote = await waha_client.create_session(session_name)
            session = WhatsAppSession(user_id=current_user.id, session_name=session_name, provider="waha",
                status=remote.get("status", "STOPPED"))
    except uazapi_client.UazapiNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except uazapi_client.UazapiAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except waha_client.WahaNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except waha_client.WahaAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
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
        if session.provider == "uazapi":
            token = decrypt_token(session.provider_token_encrypted or "")
            remote = await uazapi_client.connect(token)
            await uazapi_client.configure_webhook(token, settings.WHATSAPP_WEBHOOK_URL)
            qr_value = remote.get("qrcode") or remote.get("qrCode") or remote.get("qr")
            session.qr_data = qr_value if isinstance(qr_value, str) else None
            raw_status = str(remote.get("status") or "connecting").lower()
            session.status = {"connected": "WORKING", "connecting": "SCAN_QR_CODE", "disconnected": "STOPPED", "hibernated": "STOPPED"}.get(raw_status, raw_status.upper())
        else:
            await waha_client.ensure_session(session.session_name)
            await waha_client.update_session_webhooks(session.session_name)
            remote = await waha_client.start_session(session.session_name)
            session.status = remote.get("status", "STARTING") if isinstance(remote, dict) else "STARTING"
    except uazapi_client.UazapiNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except uazapi_client.UazapiAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except waha_client.WahaNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except waha_client.WahaAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
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
        if session.provider == "uazapi":
            token = decrypt_token(session.provider_token_encrypted or "")
            qr = await uazapi_client.qr(token)
            value = qr.get("data") or session.qr_data
            if not value:
                raise HTTPException(status_code=409, detail="QR Code ainda não disponível. Aguarde alguns segundos.")
            return {"mimetype": qr.get("mimetype", "image/png"), "data": value}
        qr = await waha_client.get_qr(session.session_name)
    except uazapi_client.UazapiAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except waha_client.WahaNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except waha_client.WahaAPIError as exc:
        if exc.status_code == 422:
            raise HTTPException(status_code=409, detail="O WhatsApp ainda está preparando o QR Code. Aguarde alguns segundos.") from exc
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
    event_data = await request.json()
    if not isinstance(event_data, dict):
        return {"received": True, "ignored": True}
    event_type = str(event_data.get("EventType") or event_data.get("event") or "")
    if event_type in {"connection", "messages", "messages_update"}:
        instance_name = event_data.get("instanceName") or (event_data.get("instance") or {}).get("name")
        result = await db.execute(select(WhatsAppSession).where(WhatsAppSession.session_name == instance_name, WhatsAppSession.provider == "uazapi"))
        u_session = result.scalar_one_or_none()
        if u_session is None:
            return {"received": True, "ignored": True}
        try:
            token = decrypt_token(u_session.provider_token_encrypted or "")
        except RuntimeError:
            raise HTTPException(status_code=401, detail="Token inválido.")
        if not hmac.compare_digest(str(event_data.get("token") or ""), token):
            raise HTTPException(status_code=401, detail="Webhook não autorizado.")
        if event_type == "connection":
            state = ((event_data.get("instance") or {}).get("status") or "").lower()
            u_session.status = {"connected": "WORKING", "connecting": "STARTING", "disconnected": "STOPPED", "hibernated": "STOPPED"}.get(state, state.upper() or u_session.status)
            if state == "connected":
                u_session.connected_at = datetime.now(timezone.utc)
                owner = event_data.get("owner")
                if isinstance(owner, str):
                    u_session.phone_number = owner.split("@", 1)[0]
            else:
                u_session.connected_at = None
            return {"received": True, "event": event_type}
        payload = event_data.get("message") or event_data.get("data") or event_data
        if isinstance(payload, dict):
            # Normalize Uazapi webhook payload into the existing message pipeline.
            event_data = {"session": u_session.session_name, "event": "message", "payload": {
                "id": payload.get("id") or payload.get("messageid") or event_data.get("event_id"),
                "body": payload.get("text") or payload.get("body") or payload.get("content"),
                "fromMe": payload.get("fromMe") or payload.get("from_me"),
                "from": payload.get("chatid") or payload.get("sender") or payload.get("from"),
                "to": payload.get("chatid") or payload.get("recipient") or payload.get("to"),
                "timestamp": payload.get("timestamp"),
                "_data": payload,
            }}
        else:
            return {"received": True, "ignored": True}
    else:
        expected = settings.WAHA_API_KEY.get_secret_value()
        if not expected or not webhook_key or not hmac.compare_digest(webhook_key, expected):
            raise HTTPException(status_code=401, detail="Webhook não autorizado.")
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

    # Grupos não fazem parte da central individual do TexasCRM.
    # O filtro também impede que mensagens enviadas para grupos sejam importadas.
    if chat_id.endswith("@g.us"):
        return {"received": True, "ignored": True, "reason": "group"}

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
        .where(
            WhatsAppConversation.user_id == current_user.id,
            ~WhatsAppConversation.chat_id.like("%@g.us"),
        )
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
        if session.provider == "uazapi":
            remote = await uazapi_client.send_text(decrypt_token(session.provider_token_encrypted or ""), conversation.contact_phone or conversation.chat_id.split("@", 1)[0], text)
        else:
            remote = await waha_client.send_text(session.session_name, conversation.chat_id, text)
    except waha_client.WahaNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except uazapi_client.UazapiAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
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
