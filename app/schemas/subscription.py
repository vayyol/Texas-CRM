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
    """Dados cadastrais exigidos pelo Asaas para criar/atualizar o cliente."""

    plan: str
    # Dados usados somente no cadastro do cliente no Asaas; não são persistidos no TexasCRM.
    cpf_cnpj: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    address_number: Optional[str] = None
    postal_code: Optional[str] = None
    province: Optional[str] = None
    city: Optional[str] = None


class CheckoutResponse(BaseModel):
    checkout_url: str


class CancelResponse(BaseModel):
    status: str
    access_until: Optional[datetime] = None


class PortalResponse(BaseModel):
    """Legado (portal da Stripe). Não é mais usado."""

    portal_url: str
