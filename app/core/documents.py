"""
Validação de CPF/CNPJ (apenas dígitos verificadores; não consulta a Receita).
"""

from __future__ import annotations

import re


def normalize_document(value: str) -> str:
    """Remove pontos, traços e barras, deixando só os dígitos."""
    return re.sub(r"\D", "", value or "")


def _digits_ok(digits: str, weights: list[int]) -> int:
    total = sum(int(d) * w for d, w in zip(digits, weights))
    rest = total % 11
    return 0 if rest < 2 else 11 - rest


def is_valid_cpf(digits: str) -> bool:
    if len(digits) != 11 or digits == digits[0] * 11:
        return False
    first = _digits_ok(digits[:9], list(range(10, 1, -1)))
    second = _digits_ok(digits[:10], list(range(11, 1, -1)))
    return digits[9:] == f"{first}{second}"


def is_valid_cnpj(digits: str) -> bool:
    if len(digits) != 14 or digits == digits[0] * 14:
        return False
    first = _digits_ok(digits[:12], [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    second = _digits_ok(digits[:13], [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    return digits[12:] == f"{first}{second}"


def is_valid_cpf_cnpj(value: str) -> bool:
    digits = normalize_document(value)
    return is_valid_cpf(digits) or is_valid_cnpj(digits)
