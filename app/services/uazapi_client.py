"""Cliente HTTP privado para UazapiGO."""
from __future__ import annotations

import httpx

from app.config import settings


class UazapiNotConfiguredError(RuntimeError):
    pass


class UazapiAPIError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _base_url() -> str:
    url = settings.UAZAPI_BASE_URL.strip().rstrip("/")
    if not url or not settings.UAZAPI_ADMIN_TOKEN.get_secret_value():
        raise UazapiNotConfiguredError("Integração UazapiGO não configurada no backend.")
    return url


async def _request(method: str, path: str, *, token: str | None = None, admin: bool = False, json: dict | None = None):
    base = _base_url()
    headers = {"Accept": "application/json"}
    if admin:
        headers["admintoken"] = settings.UAZAPI_ADMIN_TOKEN.get_secret_value()
    elif token:
        headers["token"] = token
    if json is not None:
        headers["Content-Type"] = "application/json"
    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            response = await client.request(method, f"{base}{path}", headers=headers, json=json)
            response.raise_for_status()
            if not response.content:
                return None
            return response.json()
    except httpx.HTTPStatusError as exc:
        raise UazapiAPIError(f"UazapiGO respondeu HTTP {exc.response.status_code}.", exc.response.status_code) from exc
    except httpx.HTTPError as exc:
        raise UazapiAPIError("Não foi possível comunicar com a UazapiGO.") from exc


def _instance(payload):
    if isinstance(payload, list):
        payload = payload[0] if payload else {}
    if not isinstance(payload, dict):
        return {}
    nested = payload.get("instance")
    if isinstance(nested, dict):
        return {**payload, **nested}
    return payload


async def create_instance(name: str) -> dict:
    data = await _request("POST", "/instance/create", admin=True, json={"name": name})
    if isinstance(data, list):
        data = data[0] if data else {}
    return data if isinstance(data, dict) else {}


async def connect(token: str) -> dict:
    data = await _request("POST", "/instance/connect", token=token, json={})
    return _instance(data)


async def status(token: str) -> dict:
    data = await _request("GET", "/instance/status", token=token)
    return _instance(data)


async def qr(token: str) -> dict:
    state = await status(token)
    value = state.get("qrcode") or state.get("qrCode") or state.get("qr")
    if not value:
        # A few server builds return the QR only from connect; do not restart
        # the pairing flow here, since that can invalidate a displayed code.
        return {"status": state.get("status", "connecting"), "qr": None}
    if isinstance(value, str) and value.startswith("data:image/"):
        mime, encoded = value.split(",", 1)
        return {"mimetype": mime[5:].split(";", 1)[0], "data": encoded}
    return {"mimetype": "image/png", "data": value}


async def configure_webhook(token: str, url: str) -> dict:
    return await _request("POST", "/webhook", token=token, json={
        "enabled": True,
        "url": url,
        "events": ["messages", "messages_update", "connection"],
        "excludeMessages": ["wasSentByApi"],
    })


async def send_text(token: str, number: str, text: str) -> dict:
    return await _request("POST", "/send/text", token=token, json={"number": number, "text": text})

async def delete_instance(token: str) -> None:
    await _request("DELETE", "/instance", token=token)
