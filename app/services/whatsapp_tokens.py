"""Criptografia de tokens de instâncias WhatsApp persistidos no banco."""
from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


def _cipher() -> Fernet:
    secret = settings.SECRET_KEY.get_secret_value().encode("utf-8")
    key = base64.urlsafe_b64encode(hashlib.sha256(secret + b"texas-whatsapp-instance-token").digest())
    return Fernet(key)


def encrypt_token(token: str) -> str:
    return _cipher().encrypt(token.encode()).decode()


def decrypt_token(value: str) -> str:
    try:
        return _cipher().decrypt(value.encode()).decode()
    except (InvalidToken, ValueError) as exc:
        raise RuntimeError("Não foi possível descriptografar o token da instância. Verifique SECRET_KEY do backend.") from exc
