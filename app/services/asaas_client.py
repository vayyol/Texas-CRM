"""
Cliente HTTP mínimo da API v3 do Asaas.

* A chave (``ASAAS_API_KEY``) é lida só aqui, no backend, e nunca é registrada em log.
* Headers exigidos pela documentação: ``access_token``, ``User-Agent`` e ``Content-Type``.
* Só os endpoints necessários: clientes, checkout hospedado e remoção de assinatura.
"""

from __future__ import annotations

import logging
from decimal import Decimal

import httpx

from app.config import settings

logger = logging.getLogger("app.services.asaas")

USER_AGENT = "TexasCRM/1.0"
TIMEOUT = httpx.Timeout(20.0, connect=10.0)


class AsaasError(Exception):
    """Falha ao falar com o Asaas. ``message`` é seguro para mostrar ao usuário."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class AsaasNotConfiguredError(AsaasError):
    pass


def _api_key() -> str:
    key = settings.ASAAS_API_KEY.get_secret_value().strip()
    if not key:
        raise AsaasNotConfiguredError("Pagamentos indisponíveis no momento. Tente novamente mais tarde.")
    # Erro clássico: chave de um ambiente usada no outro (sandbox: $aact_hmlg_, produção: $aact_prod_).
    is_prod_env = settings.ASAAS_BASE_URL == "https://api.asaas.com/v3"
    if (is_prod_env and "_hmlg_" in key) or (not is_prod_env and "_prod_" in key):
        logger.error("ASAAS_API_KEY não pertence ao ambiente configurado (ASAAS_ENVIRONMENT).")
        raise AsaasNotConfiguredError("Pagamentos indisponíveis no momento. Tente novamente mais tarde.")
    return key


def _error_message(response: httpx.Response) -> str:
    """Extrai as descrições de erro do Asaas (``{"errors": [{"description": ...}]}``)."""
    try:
        errors = response.json().get("errors") or []
        texts = [str(e.get("description")) for e in errors if e.get("description")]
        if texts:
            return " ".join(texts)
    except Exception:  # noqa: BLE001 - corpo inesperado: cai na mensagem genérica
        pass
    return "Não foi possível concluir a operação com o provedor de pagamentos."


async def _request(method: str, path: str, *, json: dict | None = None, params: dict | None = None) -> httpx.Response:
    headers = {"access_token": _api_key(), "User-Agent": USER_AGENT, "Content-Type": "application/json"}
    url = f"{settings.ASAAS_BASE_URL}{path}"
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            return await client.request(method, url, headers=headers, json=json, params=params)
    except httpx.HTTPError as exc:
        logger.error("Falha de rede ao chamar o Asaas (%s %s): %s", method, path, type(exc).__name__)
        raise AsaasError("Não foi possível falar com o provedor de pagamentos. Tente novamente.") from exc


def _raise_for_status(response: httpx.Response, action: str) -> None:
    if response.is_success:
        return
    if response.status_code in (401, 403):
        # Problema de credencial/ambiente: é nosso, não do usuário. Detalhes só no log.
        logger.error("Asaas recusou a autenticação em '%s' (HTTP %s).", action, response.status_code)
        raise AsaasError("Pagamentos indisponíveis no momento. Tente novamente mais tarde.", response.status_code)
    if response.status_code >= 500:
        logger.error("Asaas indisponível em '%s' (HTTP %s).", action, response.status_code)
        raise AsaasError("O provedor de pagamentos está instável. Tente novamente em instantes.", response.status_code)
    message = _error_message(response)
    logger.warning("Asaas rejeitou '%s' (HTTP %s): %s", action, response.status_code, message)
    raise AsaasError(message, response.status_code)


async def find_customer_by_external_reference(external_reference: str) -> str | None:
    """Procura um cliente já criado para este usuário (evita duplicar, pois o Asaas permite duplicatas)."""
    response = await _request("GET", "/customers", params={"externalReference": external_reference, "limit": 1})
    _raise_for_status(response, "listar clientes")
    data = response.json().get("data") or []
    return data[0].get("id") if data else None


def _customer_payload(
    *, name: str, email: str, cpf_cnpj: str, phone: str, address: str,
    address_number: str, postal_code: str, province: str,
    external_reference: str | None = None,
) -> dict:
    """Monta os campos cadastrais aceitos pelo endpoint de clientes do Asaas."""
    payload = {
        "name": name, "email": email, "cpfCnpj": cpf_cnpj, "phone": phone,
        "address": address, "addressNumber": address_number, "postalCode": postal_code,
        "province": province,
    }
    if external_reference:
        payload["externalReference"] = external_reference
    return payload


async def create_customer(
    *, name: str, email: str, cpf_cnpj: str, phone: str, address: str,
    address_number: str, postal_code: str, province: str,
    external_reference: str,
) -> str:
    """Cria o cliente no Asaas e devolve o id."""
    payload = _customer_payload(
        name=name, email=email, cpf_cnpj=cpf_cnpj, phone=phone, address=address,
        address_number=address_number, postal_code=postal_code, province=province,
        external_reference=external_reference,
    )
    response = await _request("POST", "/customers", json=payload)
    _raise_for_status(response, "criar cliente")
    return response.json()["id"]


async def update_customer(
    customer_id: str, *, name: str, email: str, cpf_cnpj: str, phone: str,
    address: str, address_number: str, postal_code: str, province: str,
) -> None:
    """Atualiza os dados cadastrais de um cliente já existente no Asaas."""
    payload = _customer_payload(
        name=name, email=email, cpf_cnpj=cpf_cnpj, phone=phone, address=address,
        address_number=address_number, postal_code=postal_code, province=province,
    )
    response = await _request("PUT", f"/customers/{customer_id}", json=payload)
    _raise_for_status(response, "atualizar cliente")


async def create_checkout(
    *,
    customer_id: str,
    item_name: str,
    item_description: str,
    value: Decimal,
    next_due_date: str,
    success_url: str,
    cancel_url: str,
    expired_url: str,
    minutes_to_expire: int,
    external_reference: str,
) -> tuple[str, str]:
    """Cria um checkout hospedado de assinatura mensal (cartão). Devolve ``(checkout_id, link)``."""
    payload = {
        "billingTypes": ["CREDIT_CARD"],
        "chargeTypes": ["RECURRENT"],
        "minutesToExpire": minutes_to_expire,
        "externalReference": external_reference,
        "callback": {"successUrl": success_url, "cancelUrl": cancel_url, "expiredUrl": expired_url},
        "items": [{"name": item_name, "description": item_description, "quantity": 1, "value": float(value)}],
        "customer": customer_id,
        "subscription": {"cycle": "MONTHLY", "nextDueDate": next_due_date},
    }
    response = await _request("POST", "/checkouts", json=payload)
    _raise_for_status(response, "criar checkout")
    data = response.json()
    checkout_id = data["id"]
    link = data.get("link")
    if not link:
        if settings.ASAAS_BASE_URL == "https://api.asaas.com/v3":
            link = f"https://asaas.com/checkoutSession/show?id={checkout_id}"
        else:
            link = f"https://sandbox.asaas.com/checkoutSession/show/{checkout_id}"
    return checkout_id, link


async def cancel_checkout(checkout_id: str) -> None:
    response = await _request("POST", f"/checkouts/{checkout_id}/cancel")
    _raise_for_status(response, "cancelar checkout")


async def delete_subscription(subscription_id: str) -> bool:
    """Remove a assinatura no Asaas (para as cobranças futuras). ``False`` se ela já não existe."""
    response = await _request("DELETE", f"/subscriptions/{subscription_id}")
    if response.status_code == 404:
        return False
    _raise_for_status(response, "remover assinatura")
    return True
