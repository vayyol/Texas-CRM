"""API de configurações e histórico de cobranças e follow-ups."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_active_user
from app.database import get_db
from app.models.whatsapp import WhatsAppSession
from app.models.whatsapp_followup import WhatsAppFollowupRecord
from app.services import uazapi_client
from app.services.whatsapp_tokens import decrypt_token
from app.services.whatsapp_followups import (
    FOLLOWUP_TYPES,
    ensure_user_defaults,
    send_record,
)

router = APIRouter()


class SettingUpdate(BaseModel):
    auto_enabled: bool
    message_template: str = Field(min_length=1, max_length=4000)


class SendFollowupRequest(BaseModel):
    message: str | None = Field(default=None, max_length=4000)


@router.get("")
async def get_followups_page(
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    settings = await ensure_user_defaults(db, current_user.id)
    session_result = await db.execute(
        select(WhatsAppSession).where(WhatsAppSession.user_id == current_user.id)
    )
    session = session_result.scalar_one_or_none()
    if session is not None:
        if session.provider_token_encrypted:
            try:
                remote = await uazapi_client.status(decrypt_token(session.provider_token_encrypted))
                remote_status = remote.get("status")
                if isinstance(remote_status, str):
                    session.status = {"connected": "WORKING", "connecting": "SCAN_QR_CODE", "disconnected": "STOPPED", "hibernated": "STOPPED"}.get(remote_status.lower(), remote_status.upper())
                owner = remote.get("owner") or remote.get("phone")
                if isinstance(owner, str):
                    session.phone_number = owner.split("@", 1)[0]
            except (uazapi_client.UazapiAPIError, RuntimeError):
                pass
        else:
            session.status = "STOPPED"
    records_result = await db.execute(
        select(WhatsAppFollowupRecord)
        .where(WhatsAppFollowupRecord.user_id == current_user.id)
        .order_by(WhatsAppFollowupRecord.due_at.desc(), WhatsAppFollowupRecord.created_at.desc())
        .limit(300)
    )
    records = records_result.scalars().all()
    settings_by_type = {item.followup_type: item for item in settings}
    return {
        "whatsapp": {
            "connected": bool(session and session.status == "WORKING"),
            "status": session.status if session else "DISCONNECTED",
            "phone_number": session.phone_number if session else None,
        },
        "settings": [
            {
                "type": key,
                "title": definition["title"],
                "description": definition["description"],
                "auto_enabled": settings_by_type[key].auto_enabled,
                "message_template": settings_by_type[key].message_template,
            }
            for key, definition in FOLLOWUP_TYPES.items()
        ],
        "records": [
            {
                "id": str(item.id),
                "event_key": item.event_key,
                "type": item.followup_type,
                "client_id": item.client_id,
                "customer_name": item.customer_name,
                "phone": item.phone,
                "title": item.title,
                "description": item.description,
                "message": item.message,
                "context": item.context_data or {},
                "status": item.status,
                "due_at": item.due_at,
                "sent_at": item.sent_at,
                "error": item.error,
            }
            for item in records
        ],
    }


@router.put("/settings/{followup_type}")
async def update_followup_setting(
    followup_type: str,
    body: SettingUpdate,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    if followup_type not in FOLLOWUP_TYPES:
        raise HTTPException(status_code=404, detail="Tipo de follow-up não encontrado.")
    settings = await ensure_user_defaults(db, current_user.id)
    setting = next(item for item in settings if item.followup_type == followup_type)
    if body.auto_enabled and not setting.auto_enabled:
        session_result = await db.execute(
            select(WhatsAppSession).where(WhatsAppSession.user_id == current_user.id)
        )
        session = session_result.scalar_one_or_none()
        if session is not None:
            if session.provider_token_encrypted:
                try:
                    remote = await uazapi_client.status(decrypt_token(session.provider_token_encrypted))
                    remote_status = remote.get("status")
                    if isinstance(remote_status, str):
                        session.status = {"connected": "WORKING", "connecting": "SCAN_QR_CODE", "disconnected": "STOPPED", "hibernated": "STOPPED"}.get(remote_status.lower(), remote_status.upper())
                except (uazapi_client.UazapiAPIError, RuntimeError) as exc:
                    raise HTTPException(status_code=503, detail="Não foi possível confirmar a conexão do WhatsApp.") from exc
            else:
                session.status = "STOPPED"
        if session is None or session.status != "WORKING":
            raise HTTPException(status_code=409, detail="Conecte o WhatsApp antes de ativar a automação.")
        setting.auto_enabled_at = datetime.now(timezone.utc)
    elif not body.auto_enabled:
        setting.auto_enabled_at = None
    setting.auto_enabled = body.auto_enabled
    setting.message_template = body.message_template.strip()
    await db.flush()
    return {"updated": True, "type": followup_type}


@router.post("/records/{record_id}/send")
async def send_followup_manually(
    record_id: uuid.UUID,
    body: SendFollowupRequest,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(WhatsAppFollowupRecord).where(
            WhatsAppFollowupRecord.id == record_id,
            WhatsAppFollowupRecord.user_id == current_user.id,
        )
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="Follow-up não encontrado.")
    if record.status == "dismissed":
        raise HTTPException(status_code=409, detail="Este follow-up foi dispensado.")
    success, error = await send_record(db, record, body.message)
    if not success:
        return {"sent": False, "error": error, "status": record.status}
    return {"sent": True, "sent_at": record.sent_at}


@router.post("/records/{record_id}/dismiss")
async def dismiss_followup(
    record_id: uuid.UUID,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(WhatsAppFollowupRecord).where(
            WhatsAppFollowupRecord.id == record_id,
            WhatsAppFollowupRecord.user_id == current_user.id,
        )
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="Follow-up não encontrado.")
    if record.status == "sent":
        raise HTTPException(status_code=409, detail="Uma mensagem já enviada não pode ser dispensada.")
    record.status = "dismissed"
    record.dismissed_at = datetime.now(timezone.utc)
    record.auto_send_pending = False
    return {"dismissed": True}
