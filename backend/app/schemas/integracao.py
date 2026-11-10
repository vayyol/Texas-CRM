
from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class CadastroClienteSchema(BaseModel):
    nome: str
    email: str | None = None
    telefone: str
    status: bool = False



class DescricaoSchema(BaseModel):
    descricao: str


class EstadoValueSchema(BaseModel):
    descricao: str
    forma_pagamento: str | None = None
    valor_total: Decimal | None = None
    quantidade: int | None = None
    data_vencimento: date | None = None
    quant_quitada: int | None = None

