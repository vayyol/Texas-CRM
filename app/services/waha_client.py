"""Cliente HTTP privado para o serviÃ§o WAHA."""
from __future__ import annotations

import httpx

from app.config import settings


class WahaNotConfiguredError(RuntimeError):
    pass


class WahaAPIError(RuntimeError):
    pass


def _configuration() -> tuple[str, str]:
    base_url = settings.WAHA_BASE_URL.strip().rstrip("/")
    api_key = settings.WAHA_API_KEY.get_secret_value()
    if not base_url or not api_key:
        raise WahaNotConfiguredError("IntegraÃ§Ã£o WAHA nÃ£o configurada no backend.")
    return base_url, api_key


async def _request(method: str, path: str, **kwargs):
    base_url, api_key = _configuration()
    headers = kwargs.pop("headers", {})
    headers["X-Api-Key"] = api_key
    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            response = await client.request(method, f"{base_url}{path}", headers=headers, **kwargs)
            response.raise_for_status()
            if response.status_code == 204 or not response.content:
                return None
            return response.json()
    except httpx.HTTPStatusError as exc:
        # NÃ£o propaga corpo da resposta, que pode conter dados operacionais.
        raise WahaAPIError(f"WAHA respondeu HTTP {exc.response.status_code}.") from exc
    except httpx.HTTPError as exc:
        raise WahaAPIError("NÃ£o foi possÃ­vel comunicar com o serviÃ§o WAHA.") from exc


async def create_session(name: str) -> dict:
    return await _request("POST", "/api/sessions", json={"name": name, "start": False})


async def get_session(name: str) -> dict:
    return await _request("GET", f"/api/sessions/{name}")


async def start_session(name: str) -> dict:
    return await _request("POST", f"/api/sessions/{name}/start", json={})


async def get_qr(name: str) -> dict:
    return await _request(
        "GET",
        f"/api/{name}/auth/qr?format=raw",
        headers={"Accept": "application/json"},
    )


async def delete_session(name: str) -> None:
    await _request("DELETE", f"/api/sessions/{name}")

