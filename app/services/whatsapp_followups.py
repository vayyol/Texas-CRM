"""Geração, registro e envio automático de cobranças e follow-ups."""
from __future__ import annotations

import asyncio
import logging
import os
import re
from datetime import date, datetime, time, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.integration_security import gerar_token_integracao
from app.database import async_session_factory
from app.models.whatsapp import WhatsAppConversation, WhatsAppMessage, WhatsAppSession
from app.models.whatsapp_followup import (
    WhatsAppFollowupCursor,
    WhatsAppFollowupRecord,
    WhatsAppFollowupSetting,
)
from app.services import uazapi_client
from app.services.whatsapp_tokens import decrypt_token

logger = logging.getLogger(__name__)
LOCAL_TZ = timezone(timedelta(hours=-3))  # Horário de Brasília (sem horário de verão)
POLL_SECONDS = 60

FOLLOWUP_TYPES = {
    "sale_completed": {
        "title": "Venda realizada",
        "description": "Confirmação da venda com o valor total.",
        "default_message": (
            "Olá, {nome}! Sua compra foi registrada com sucesso no valor de {valor_venda}. "
            "Obrigado pela preferência! Se precisar de algo, estou à disposição."
        ),
    },
    "installment_overdue": {
        "title": "Parcela vencida",
        "description": "Cobrança de uma parcela na data de vencimento.",
        "default_message": (
            "Olá, {nome}! Tudo bem? A parcela {parcela} da sua compra ({descricao}) "
            "venceu em {data_vencimento} e tem o valor de {valor_parcela}. "
            "Poderia nos informar quando conseguirá realizar o pagamento? "
            "Se já pagou, por favor desconsidere esta mensagem. Obrigado!"
        ),
    },
    "sale_lost": {
        "title": "Venda não realizada",
        "description": "Tentativa de recuperar o cliente após 5 dias.",
        "default_message": (
            "Olá, {nome}! Tudo bem? Vi que não conseguimos concluir nossa negociação "
            "sobre {descricao}. Gostaria de saber se ainda posso ajudar ou se ficou "
            "alguma dúvida. Estou à disposição!"
        ),
    },
    "proposal_no_reply": {
        "title": "Orçamento sem resposta",
        "description": "Acompanhamento de orçamento aberto após 1 dia.",
        "default_message": (
            "Olá, {nome}! Tudo bem? Gostaria de saber se conseguiu analisar o orçamento "
            "de {descricao}, no valor de {valor_venda}. Se tiver alguma dúvida ou quiser "
            "conversar sobre a proposta, estou à disposição!"
        ),
    },
    "proposal_created": {
        "title": "Enviar orçamento",
        "description": "Envie o orçamento ao cliente assim que ele for criado.",
        "default_message": (
            "Olá, {nome}! Preparei o orçamento de {descricao}, no valor de {valor_venda}. "
            "Estou enviando para você analisar. Qualquer dúvida, estou à disposição!"
        ),
    },
    "client_stage_idle": {
        "title": "Retomar contato",
        "description": "Contato, interessado ou desinteressado sem movimentação há 2 dias.",
        "default_message": (
            "Olá, {nome}! Tudo bem? Estou passando para saber se podemos dar continuidade "
            "à nossa conversa sobre {descricao}. Se precisar de algo, conte comigo!"
        ),
    },
}


def _parse_datetime(value) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _parse_date(value) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _money(value) -> str:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        number = 0
    return ("R$ {:,.2f}".format(number)).replace(",", "X").replace(".", ",").replace("X", ".")


def _render_message(template: str, context: dict) -> str:
    values = {key: str(value if value is not None else "") for key, value in context.items()}
    return re.sub(r"\{([a-zA-Z_]+)\}", lambda match: values.get(match.group(1), match.group(0)), template)


def normalize_phone(phone: str | None) -> str | None:
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) in (10, 11):
        digits = "55" + digits
    if len(digits) < 12 or len(digits) > 15:
        return None
    return digits


async def ensure_user_defaults(db: AsyncSession, user_id) -> list[WhatsAppFollowupSetting]:
    result = await db.execute(
        select(WhatsAppFollowupSetting).where(WhatsAppFollowupSetting.user_id == user_id)
    )
    existing = {item.followup_type: item for item in result.scalars().all()}
    for followup_type, definition in FOLLOWUP_TYPES.items():
        if followup_type not in existing:
            setting = WhatsAppFollowupSetting(
                user_id=user_id,
                followup_type=followup_type,
                auto_enabled=False,
                message_template=definition["default_message"],
            )
            db.add(setting)
            existing[followup_type] = setting
    cursor_result = await db.execute(
        select(WhatsAppFollowupCursor).where(WhatsAppFollowupCursor.user_id == user_id)
    )
    if cursor_result.scalar_one_or_none() is None:
        db.add(WhatsAppFollowupCursor(user_id=user_id, last_scanned_at=datetime.now(timezone.utc)))
    await db.flush()
    return list(existing.values())


async def _fetch_crm_data(user_id) -> tuple[list[dict], list[dict]]:
    api_url = os.getenv("CLIENTES_API_URL", "http://host.docker.internal:8001").rstrip("/")
    api_key = os.getenv("CLIENTES_API_KEY")
    if not api_key:
        raise RuntimeError("Chave de integração com a API de clientes não configurada.")
    token = gerar_token_integracao(user_id)
    headers = {"X-API-Key": api_key, "X-User-Token": token}
    async with httpx.AsyncClient(timeout=20.0) as client:
        clients_response, dashboard_response = await asyncio.gather(
            client.get(f"{api_url}/order/listar-clientes-estados", headers=headers),
            client.get(f"{api_url}/order/dashboard-acompanhamento", headers=headers),
        )
        clients_response.raise_for_status()
        dashboard_response.raise_for_status()
    clients = clients_response.json()
    dashboard = dashboard_response.json()
    return (
        clients if isinstance(clients, list) else [],
        dashboard.get("pagamentos", []) if isinstance(dashboard, dict) else [],
    )


def _build_candidates(clients: list[dict], payments: list[dict], cursor: datetime, now: datetime):
    candidates = []
    for client in clients:
        if not isinstance(client, dict):
            continue
        client_id = client.get("id")
        name = str(client.get("nome") or "Cliente")
        phone = client.get("telefone")
        for state in client.get("estados") or []:
            if not isinstance(state, dict) or not state.get("id"):
                continue
            state_type = state.get("tipo")
            created_at = _parse_datetime(state.get("created_at"))
            if not created_at:
                continue
            description = str(state.get("descricao") or "sua compra")
            value = _money(state.get("valor_total"))
            context = {"nome": name, "descricao": description, "valor_venda": value}
            state_status = state.get("status")
            state_candidates = []
            if state_type == "VENDA_REALIZADA":
                state_candidates.append((created_at, "sale_completed", f"sale:{state['id']}"))
            elif state_type == "VENDA_NAO_REALIZADA":
                state_candidates.append((created_at + timedelta(days=5), "sale_lost", f"lost:{state['id']}"))
            elif state_type == "PROPOSTA" and state_status == "ABERTO":
                # O envio do orçamento é imediato; o lembrete por falta de resposta vem após 1 dia.
                state_candidates.append((created_at, "proposal_created", f"proposal-created:{state['id']}"))
                state_candidates.append((created_at + timedelta(days=1), "proposal_no_reply", f"proposal-no-reply:{state['id']}"))
            elif state_type in {"CONTATO", "INTERESSADO", "DESINTERESSADO"} and state_status == "ABERTO":
                state_candidates.append((created_at + timedelta(days=2), "client_stage_idle", f"stage-idle:{state['id']}"))
            for eligible_at, followup_type, event_key in state_candidates:
                if cursor < eligible_at <= now:
                    candidates.append({
                        "event_key": event_key, "followup_type": followup_type,
                        "client_id": int(client_id), "customer_name": name, "phone": phone,
                        "title": FOLLOWUP_TYPES[followup_type]["title"],
                        "description": FOLLOWUP_TYPES[followup_type]["description"],
                        "context": context, "due_at": eligible_at,
                    })

    today_local = datetime.now(LOCAL_TZ).date()
    for payment in payments:
        if not isinstance(payment, dict):
            continue
        due_date = _parse_date(payment.get("data_vencimento"))
        if not due_date or due_date > today_local:
            continue
        due_at = datetime.combine(due_date, time.min, tzinfo=LOCAL_TZ).astimezone(timezone.utc)
        client_id = payment.get("client_id")
        sale_id = payment.get("id_venda")
        if client_id is None or sale_id is None:
            continue
        name = str(payment.get("nome") or "Cliente")
        description = str(payment.get("descricao") or "sua compra")
        installment = payment.get("proxima_parcela") or 1
        amount = _money(payment.get("valor_parcela"))
        context = {
            "nome": name, "descricao": description, "parcela": installment,
            "valor_parcela": amount, "data_vencimento": due_date.strftime("%d/%m/%Y"),
        }
        candidates.append({
            "event_key": f"installment:{sale_id}:{installment}:{due_date.isoformat()}",
            "followup_type": "installment_overdue",
            "client_id": int(client_id), "customer_name": name,
            "phone": payment.get("telefone"),
            "title": FOLLOWUP_TYPES["installment_overdue"]["title"],
            "description": f"Parcela {installment} de {description}, vencida em {due_date.strftime('%d/%m/%Y')}.",
            "context": context, "due_at": due_at,
        })
    return candidates


async def send_record(db: AsyncSession, record: WhatsAppFollowupRecord, message: str | None = None) -> tuple[bool, str | None]:
    session_result = await db.execute(
        select(WhatsAppSession).where(WhatsAppSession.user_id == record.user_id)
    )
    session = session_result.scalar_one_or_none()
    if session is None or session.status != "WORKING":
        return False, "Conecte o WhatsApp para enviar esta mensagem."
    phone = normalize_phone(record.phone)
    if not phone:
        record.status = "failed"
        record.auto_send_pending = False
        record.error = "O cliente não possui um telefone válido cadastrado."
        return False, record.error
    text = (message if message is not None else record.message).strip()
    if not text:
        return False, "A mensagem não pode estar vazia."
    chat_id = f"{phone}@c.us"
    if not session.provider_token_encrypted:
        return False, "A sessão UazapiGO ainda não foi inicializada. Reconecte o WhatsApp."
    try:
        remote = await uazapi_client.send_text(decrypt_token(session.provider_token_encrypted), phone, text)
    except (uazapi_client.UazapiAPIError, uazapi_client.UazapiNotConfiguredError, RuntimeError) as exc:
        record.status = "failed"
        record.auto_send_pending = False
        record.error = str(exc)
        return False, str(exc)

    conversation_result = await db.execute(
        select(WhatsAppConversation).where(
            WhatsAppConversation.user_id == record.user_id,
            WhatsAppConversation.session_id == session.id,
            WhatsAppConversation.chat_id == chat_id,
        )
    )
    conversation = conversation_result.scalar_one_or_none()
    if conversation is None:
        conversation = WhatsAppConversation(
            user_id=record.user_id, session_id=session.id, chat_id=chat_id,
            contact_name=record.customer_name, contact_phone=phone,
        )
        db.add(conversation)
        await db.flush()
    timestamp = remote.get("timestamp") if isinstance(remote, dict) else None
    sent_at = datetime.fromtimestamp(timestamp, tz=timezone.utc) if isinstance(timestamp, (int, float)) else datetime.now(timezone.utc)
    message_id = remote.get("id") if isinstance(remote, dict) else None
    db.add(WhatsAppMessage(
        user_id=record.user_id, conversation_id=conversation.id,
        provider_message_id=message_id if isinstance(message_id, str) else None,
        direction="out", body=text, message_type="text", status="sent", sent_at=sent_at,
    ))
    conversation.last_message_at = sent_at
    conversation.last_message_preview = text[:500]
    record.message = text
    record.status = "sent"
    record.sent_at = sent_at
    record.error = None
    record.auto_send_pending = False
    return True, None


async def process_user(db: AsyncSession, user_id) -> None:
    settings = await ensure_user_defaults(db, user_id)
    settings_by_type = {item.followup_type: item for item in settings}
    cursor_result = await db.execute(
        select(WhatsAppFollowupCursor).where(WhatsAppFollowupCursor.user_id == user_id)
    )
    cursor = cursor_result.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if cursor is None:
        cursor = WhatsAppFollowupCursor(
            user_id=user_id,
            last_scanned_at=now,
            initialized=False,
        )
        db.add(cursor)
        await db.flush()

    clients, payments = await _fetch_crm_data(user_id)
    if cursor.initialized:
        candidates = _build_candidates(clients, payments, cursor.last_scanned_at, now)
        historical_candidates = []
    else:
        # Na primeira leitura, registra pendências que já existiam sem disparar
        # mensagens antigas automaticamente. Venda realizada é um aviso imediato
        # e não deve gerar uma confirmação retroativa.
        all_candidates = _build_candidates(
            clients,
            payments,
            datetime.min.replace(tzinfo=timezone.utc),
            now,
        )
        historical_candidates = [
            item for item in all_candidates
            if item["due_at"] <= cursor.last_scanned_at
            and item["followup_type"] != "sale_completed"
        ]
        candidates = [
            item for item in all_candidates
            if item["due_at"] > cursor.last_scanned_at
        ]

    async def register_candidate(candidate: dict, allow_automatic: bool) -> None:
        exists = await db.execute(
            select(WhatsAppFollowupRecord.id).where(
                WhatsAppFollowupRecord.user_id == user_id,
                WhatsAppFollowupRecord.event_key == candidate["event_key"],
            )
        )
        if exists.scalar_one_or_none():
            return
        setting = settings_by_type[candidate["followup_type"]]
        template = setting.message_template or FOLLOWUP_TYPES[candidate["followup_type"]]["default_message"]
        auto_eligible = bool(
            allow_automatic
            and setting.auto_enabled
            and setting.auto_enabled_at
            and candidate["due_at"] >= setting.auto_enabled_at
        )
        record = WhatsAppFollowupRecord(
            user_id=user_id,
            event_key=candidate["event_key"],
            followup_type=candidate["followup_type"],
            client_id=candidate["client_id"],
            customer_name=candidate["customer_name"],
            phone=candidate["phone"],
            title=candidate["title"],
            description=candidate["description"],
            message=_render_message(template, candidate["context"]),
            context_data=candidate["context"],
            status="pending",
            auto_send_pending=auto_eligible,
            due_at=candidate["due_at"],
        )
        db.add(record)
        await db.flush()
        if auto_eligible:
            success, error = await send_record(db, record)
            if not success and error:
                record.error = error

    for candidate in historical_candidates:
        await register_candidate(candidate, allow_automatic=False)
    for candidate in candidates:
        await register_candidate(candidate, allow_automatic=True)

    # Retoma envios automáticos que aguardavam a reconexão do WhatsApp.
    pending_result = await db.execute(
        select(WhatsAppFollowupRecord).where(
            WhatsAppFollowupRecord.user_id == user_id,
            WhatsAppFollowupRecord.status == "pending",
            WhatsAppFollowupRecord.auto_send_pending.is_(True),
        )
    )
    for record in pending_result.scalars().all():
        setting = settings_by_type.get(record.followup_type)
        if (
            not setting
            or not setting.auto_enabled
            or not setting.auto_enabled_at
            or record.due_at < setting.auto_enabled_at
        ):
            record.auto_send_pending = False
            continue
        await send_record(db, record)

    cursor.last_scanned_at = now
    cursor.initialized = True
    await db.flush()


async def followup_scheduler() -> None:
    """Varre situações elegíveis e processa os envios automáticos."""
    while True:
        try:
            async with async_session_factory() as db:
                result = await db.execute(select(WhatsAppFollowupSetting.user_id).distinct())
                user_ids = result.scalars().all()
                for user_id in user_ids:
                    try:
                        await process_user(db, user_id)
                        await db.commit()
                    except Exception:
                        await db.rollback()
                        logger.exception("Falha ao processar follow-ups do usuário %s", user_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Falha no ciclo do agendador de follow-ups")
        await asyncio.sleep(POLL_SECONDS)
