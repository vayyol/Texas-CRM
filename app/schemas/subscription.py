import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class PlanFeature(BaseModel):
    name: str
    included: bool = True
    limit: Optional[str] = None


class PlanResponse(BaseModel):
    name: str
    display_name: str
    price_monthly: float
    price_id: Optional[str] = None  # legado (Stripe); sempre nulo com o Asaas
    purchasable: bool = False
    features: List[PlanFeature] = []
    is_popular: bool = False


class SubscriptionResponse(BaseModel):
    id: uuid.UUID
    plan_name: str
    status: str
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    created_at: datetime
    model_config = {"from_attributes": True}


class CheckoutRequest(BaseModel):
    """O frontend informa só o plano. Valor e URLs de retorno são definidos pelo backend."""

    plan: str
    # CPF ou CNPJ: exigido pelo Asaas para criar o cliente. Não é gravado no nosso banco.
    cpf_cnpj: Optional[str] = None


class CheckoutResponse(BaseModel):
    checkout_url: str


class CancelResponse(BaseModel):
    status: str
    access_until: Optional[datetime] = None


class PortalResponse(BaseModel):
    """Legado (portal da Stripe). Não é mais usado."""

    portal_url: str
