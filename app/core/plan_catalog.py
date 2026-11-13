"""
Catálogo de planos do Texas CRM.

Os preços vivem SOMENTE aqui (backend). O frontend informa apenas o identificador do plano
(``pro``) e nunca o valor da cobrança.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.schemas.subscription import PlanFeature, PlanResponse


@dataclass(frozen=True)
class PlanDefinition:
    name: str
    display_name: str
    price_monthly: Decimal
    purchasable: bool
    is_popular: bool
    features: tuple[tuple[str, bool], ...]


PLANS: dict[str, PlanDefinition] = {
    "free": PlanDefinition(
        name="free",
        display_name="Free",
        price_monthly=Decimal("0.00"),
        purchasable=False,  # o Free não tem cobrança
        is_popular=False,
        features=(
            ("Até 5 clientes cadastrados", True),
            ("Edição de clientes cadastrados", True),
            ("Registro do relacionamento com os clientes", True),
            ("Análise de estatísticas", True),
            ("Suporte prioritário", False),
        ),
    ),
    "pro": PlanDefinition(
        name="pro",
        display_name="Pro",
        price_monthly=Decimal("24.90"),
        purchasable=True,
        is_popular=True,
        features=(
            ("Cadastro ilimitado de clientes", True),
            ("Edição de clientes cadastrados", True),
            ("Registro do relacionamento com os clientes", True),
            ("Análise de estatísticas", True),
            ("Suporte prioritário", True),
        ),
    ),
    "enterprise": PlanDefinition(
        name="enterprise",
        display_name="Enterprise",
        price_monthly=Decimal("99.00"),
        purchasable=False,  # indisponível até ser configurado
        is_popular=False,
        features=(
            ("Clientes ilimitados", True),
            ("Tudo do plano Pro", True),
            ("Painel administrativo", True),
            ("SLA garantido", True),
        ),
    ),
}


def get_plan(name: str) -> PlanDefinition | None:
    return PLANS.get(name)


def list_plans() -> list[PlanResponse]:
    """Planos no formato devolvido por ``GET /subscriptions/plans``."""
    return [
        PlanResponse(
            name=plan.name,
            display_name=plan.display_name,
            price_monthly=float(plan.price_monthly),
            price_id=None,
            purchasable=plan.purchasable,
            is_popular=plan.is_popular,
            features=[PlanFeature(name=label, included=included) for label, included in plan.features],
        )
        for plan in PLANS.values()
    ]
