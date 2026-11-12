"""Integração com a API externa de clientes."""

import os

import httpx
from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_active_user
from app.core.integration_security import gerar_token_integracao
from app.core.plans import FREE_CLIENT_LIMIT, get_user_plan
from app.database import get_db
from app.schemas.integracao import CadastroClienteSchema, DescricaoSchema, EstadoValueSchema

router = APIRouter()


@router.get("/teste")
async def testar_integracao(
    current_user=Depends(get_current_active_user),
):
    api_url = os.getenv(
        "CLIENTES_API_URL",
        "http://host.docker.internal:8001",
    ).rstrip("/")

    api_key = os.getenv("CLIENTES_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="Chave de integração não configurada.",
        )

    token = gerar_token_integracao(current_user.id)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{api_url}/order/teste-usuario",
                headers={
                    "X-API-Key": api_key,
                    "X-User-Token": token,
                },
            )

        response.raise_for_status()

        return {
            "message": "Integração funcionando!",
            "usuario_id": str(current_user.id),
            "api_resposta": response.json(),
        }

    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=(f"A API de clientes retornou HTTP {exc.response.status_code}."),
        )
    except httpx.RequestError:
        raise HTTPException(
            status_code=502,
            detail="Não foi possível conectar à API de clientes.",
        )


@router.post("/cadastro-cliente")
async def cadastrar_cliente(
    schema: CadastroClienteSchema,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    api_url = os.getenv(
        "CLIENTES_API_URL",
        "http://host.docker.internal:8001",
    ).rstrip("/")

    api_key = os.getenv("CLIENTES_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="Chave de integração não configurada.",
        )

    token = gerar_token_integracao(current_user.id)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Plano free: limite de clientes (conta ativos e inativos).
            plano = await get_user_plan(db, current_user.id)
            if plano == "free":
                listagem = await client.get(
                    f"{api_url}/order/listar-clientes",
                    headers={
                        "X-API-Key": api_key,
                        "X-User-Token": token,
                    },
                )
                total_clientes = 0
                if listagem.status_code != 404:
                    listagem.raise_for_status()
                    dados = listagem.json()
                    total_clientes = len(dados) if isinstance(dados, list) else 0

                if total_clientes >= FREE_CLIENT_LIMIT:
                    raise HTTPException(
                        status_code=403,
                        detail=(
                            f"O plano Free permite cadastrar até {FREE_CLIENT_LIMIT} "
                            "clientes. Faça upgrade para cadastrar mais."
                        ),
                    )

            response = await client.post(
                f"{api_url}/order/cadastro-cliente",
                headers={
                    "X-API-Key": api_key,
                    "X-User-Token": token,
                },
                json=schema.model_dump(),
            )

        response.raise_for_status()
        return response.json()

    except httpx.HTTPStatusError as exc:
        try:
            detalhe = exc.response.json()
        except ValueError:
            detalhe = "Erro retornado pela API de clientes."

        raise HTTPException(
            status_code=exc.response.status_code,
            detail=detalhe,
        )

    except httpx.RequestError:
        raise HTTPException(
            status_code=502,
            detail="Não foi possível conectar à API de clientes.",
        )


@router.post("/contato-cliente/{id_client}")
async def contato_cliente(
    id_client: int,
    schema: DescricaoSchema,
    current_user=Depends(get_current_active_user),
):
    api_url = os.getenv(
        "CLIENTES_API_URL",
        "http://host.docker.internal:8001",
    ).rstrip("/")

    api_key = os.getenv("CLIENTES_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="Chave de integração não configurada.",
        )

    token = gerar_token_integracao(current_user.id)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{api_url}/order/contato-cliente/{id_client}",
                headers={
                    "X-API-Key": api_key,
                    "X-User-Token": token,
                },
                json=schema.model_dump(),
            )

        response.raise_for_status()
        return response.json()

    except httpx.HTTPStatusError as exc:
        try:
            detalhe = exc.response.json()
        except ValueError:
            detalhe = "Erro retornado pela API de clientes."

        raise HTTPException(
            status_code=exc.response.status_code,
            detail=detalhe,
        )

    except httpx.RequestError:
        raise HTTPException(
            status_code=502,
            detail="Não foi possível conectar à API de clientes.",
        )


@router.post("/interessado-cliente/{id_client}")
async def interessado_cliente(
    id_client: int,
    schema: DescricaoSchema,
    current_user=Depends(get_current_active_user),
):
    api_url = os.getenv(
        "CLIENTES_API_URL",
        "http://host.docker.internal:8001",
    ).rstrip("/")

    api_key = os.getenv("CLIENTES_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="Chave de integração não configurada.",
        )

    token = gerar_token_integracao(current_user.id)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{api_url}/order/interessado-cliente/{id_client}",
                headers={
                    "X-API-Key": api_key,
                    "X-User-Token": token,
                },
                json=schema.model_dump(),
            )

        response.raise_for_status()
        return response.json()

    except httpx.HTTPStatusError as exc:
        try:
            detalhe = exc.response.json()
        except ValueError:
            detalhe = "Erro retornado pela API de clientes."

        raise HTTPException(
            status_code=exc.response.status_code,
            detail=detalhe,
        )

    except httpx.RequestError:
        raise HTTPException(
            status_code=502,
            detail="Não foi possível conectar à API de clientes.",
        )


@router.post("/desinteressado-cliente/{id_client}")
async def desinteressado_cliente(
    id_client: int,
    schema: DescricaoSchema,
    current_user=Depends(get_current_active_user),
):
    api_url = os.getenv(
        "CLIENTES_API_URL",
        "http://host.docker.internal:8001",
    ).rstrip("/")

    api_key = os.getenv("CLIENTES_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="Chave de integração não configurada.",
        )

    token = gerar_token_integracao(current_user.id)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{api_url}/order/desinteressado-cliente/{id_client}",
                headers={
                    "X-API-Key": api_key,
                    "X-User-Token": token,
                },
                json=schema.model_dump(),
            )

        response.raise_for_status()
        return response.json()

    except httpx.HTTPStatusError as exc:
        try:
            detalhe = exc.response.json()
        except ValueError:
            detalhe = "Erro retornado pela API de clientes."

        raise HTTPException(
            status_code=exc.response.status_code,
            detail=detalhe,
        )

    except httpx.RequestError:
        raise HTTPException(
            status_code=502,
            detail="Não foi possível conectar à API de clientes.",
        )


@router.post("/proposta-cliente/{id_client}")
async def proposta_cliente(
    id_client: int,
    schema: EstadoValueSchema,
    current_user=Depends(get_current_active_user),
):
    api_url = os.getenv(
        "CLIENTES_API_URL",
        "http://host.docker.internal:8001",
    ).rstrip("/")

    api_key = os.getenv("CLIENTES_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="Chave de integração não configurada.",
        )

    token = gerar_token_integracao(current_user.id)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{api_url}/order/proposta-cliente/{id_client}",
                headers={
                    "X-API-Key": api_key,
                    "X-User-Token": token,
                },
                json=schema.model_dump(mode="json"),
            )

        response.raise_for_status()
        return response.json()

    except httpx.HTTPStatusError as exc:
        try:
            detalhe = exc.response.json()
        except ValueError:
            detalhe = "Erro retornado pela API de clientes."

        raise HTTPException(
            status_code=exc.response.status_code,
            detail=detalhe,
        )

    except httpx.RequestError:
        raise HTTPException(
            status_code=502,
            detail="Não foi possível conectar à API de clientes.",
        )


@router.post("/venda-nao-realizada/{id_client}")
async def venda_nao_realizada(
    id_client: int,
    schema: DescricaoSchema,
    current_user=Depends(get_current_active_user),
):
    api_url = os.getenv(
        "CLIENTES_API_URL",
        "http://host.docker.internal:8001",
    ).rstrip("/")

    api_key = os.getenv("CLIENTES_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="Chave de integração não configurada.",
        )

    token = gerar_token_integracao(current_user.id)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{api_url}/order/venda-nao-realizada/{id_client}",
                headers={
                    "X-API-Key": api_key,
                    "X-User-Token": token,
                },
                json=schema.model_dump(),
            )

        response.raise_for_status()
        return response.json()

    except httpx.HTTPStatusError as exc:
        try:
            detalhe = exc.response.json()
        except ValueError:
            detalhe = "Erro retornado pela API de clientes."

        raise HTTPException(
            status_code=exc.response.status_code,
            detail=detalhe,
        )

    except httpx.RequestError:
        raise HTTPException(
            status_code=502,
            detail="Não foi possível conectar à API de clientes.",
        )


@router.post("/venda-realizada/{id_client}")
async def venda_realizada(
    id_client: int,
    schema: EstadoValueSchema,
    current_user=Depends(get_current_active_user),
):
    api_url = os.getenv(
        "CLIENTES_API_URL",
        "http://host.docker.internal:8001",
    ).rstrip("/")

    api_key = os.getenv("CLIENTES_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="Chave de integração não configurada.",
        )

    token = gerar_token_integracao(current_user.id)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{api_url}/order/venda-realizada/{id_client}",
                headers={
                    "X-API-Key": api_key,
                    "X-User-Token": token,
                },
                json=schema.model_dump(mode="json"),
            )

        response.raise_for_status()
        return response.json()

    except httpx.HTTPStatusError as exc:
        try:
            detalhe = exc.response.json()
        except ValueError:
            detalhe = "Erro retornado pela API de clientes."

        raise HTTPException(
            status_code=exc.response.status_code,
            detail=detalhe,
        )

    except httpx.RequestError:
        raise HTTPException(
            status_code=502,
            detail="Não foi possível conectar à API de clientes.",
        )


@router.post("/quitar-venda/{id_client}/{id_venda}/{quant_quitada}")
async def quitar_venda(
    id_client: int,
    id_venda: int,
    quant_quitada: int,
    current_user=Depends(get_current_active_user),
):
    api_url = os.getenv(
        "CLIENTES_API_URL",
        "http://host.docker.internal:8001",
    ).rstrip("/")

    api_key = os.getenv("CLIENTES_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="Chave de integração não configurada.",
        )

    token = gerar_token_integracao(current_user.id)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{api_url}/order/quitar-venda/{id_client}/{id_venda}/{quant_quitada}",
                headers={
                    "X-API-Key": api_key,
                    "X-User-Token": token,
                },
            )

        response.raise_for_status()
        return response.json()

    except httpx.HTTPStatusError as exc:
        try:
            detalhe = exc.response.json()
        except ValueError:
            detalhe = "Erro retornado pela API de clientes."

        raise HTTPException(
            status_code=exc.response.status_code,
            detail=detalhe,
        )

    except httpx.RequestError:
        raise HTTPException(
            status_code=502,
            detail="Não foi possível conectar à API de clientes.",
        )


# ROTAS GET


@router.get("/listar-clientes")
async def listar_clientes(
    current_user=Depends(get_current_active_user),
):
    api_url = os.getenv(
        "CLIENTES_API_URL",
        "http://host.docker.internal:8001",
    ).rstrip("/")

    api_key = os.getenv("CLIENTES_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="Chave de integração não configurada.",
        )

    token = gerar_token_integracao(current_user.id)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{api_url}/order/listar-clientes",
                headers={
                    "X-API-Key": api_key,
                    "X-User-Token": token,
                },
            )

        response.raise_for_status()
        return response.json()

    except httpx.HTTPStatusError as exc:
        try:
            detalhe = exc.response.json()
        except ValueError:
            detalhe = "Erro retornado pela API de clientes."

        raise HTTPException(
            status_code=exc.response.status_code,
            detail=detalhe,
        )

    except httpx.RequestError:
        raise HTTPException(
            status_code=502,
            detail="Não foi possível conectar à API de clientes.",
        )


@router.get("/listar-estados/{id_client}")
async def listar_estados_cliente(
    id_client: int,
    current_user=Depends(get_current_active_user),
):

    api_url = os.getenv(
        "CLIENTES_API_URL",
        "http://host.docker.internal:8001",
    ).rstrip("/")

    api_key = os.getenv("CLIENTES_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="Chave de integração não configurada.",
        )

    token = gerar_token_integracao(current_user.id)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{api_url}/order/listar-estados/{id_client}",
                headers={
                    "X-API-Key": api_key,
                    "X-User-Token": token,
                },
            )

        response.raise_for_status()
        return response.json()

    except httpx.HTTPStatusError as exc:
        try:
            detalhe = exc.response.json()
        except ValueError:
            detalhe = "Erro retornado pela API de clientes."

        raise HTTPException(
            status_code=exc.response.status_code,
            detail=detalhe,
        )

    except httpx.RequestError:
        raise HTTPException(
            status_code=502,
            detail="Não foi possível conectar à API de clientes.",
        )


@router.get("/listar-clientes-estados")
async def listar_clientes_estados(
    current_user=Depends(get_current_active_user),
):

    api_url = os.getenv(
        "CLIENTES_API_URL",
        "http://host.docker.internal:8001",
    ).rstrip("/")

    api_key = os.getenv("CLIENTES_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="Chave de integração não configurada.",
        )

    token = gerar_token_integracao(current_user.id)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{api_url}/order/listar-clientes-estados",
                headers={
                    "X-API-Key": api_key,
                    "X-User-Token": token,
                },
            )

        response.raise_for_status()
        return response.json()

    except httpx.HTTPStatusError as exc:
        try:
            detalhe = exc.response.json()
        except ValueError:
            detalhe = "Erro retornado pela API de clientes."

        raise HTTPException(
            status_code=exc.response.status_code,
            detail=detalhe,
        )

    except httpx.RequestError:
        raise HTTPException(
            status_code=502,
            detail="Não foi possível conectar à API de clientes.",
        )


@router.get("/consultar-estado/{id_estado}")
async def consultar_estado(
    id_estado: int,
    current_user=Depends(get_current_active_user),
):

    api_url = os.getenv(
        "CLIENTES_API_URL",
        "http://host.docker.internal:8001",
    ).rstrip("/")

    api_key = os.getenv("CLIENTES_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="Chave de integração não configurada.",
        )

    token = gerar_token_integracao(current_user.id)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{api_url}/order/consultar-estado/{id_estado}",
                headers={
                    "X-API-Key": api_key,
                    "X-User-Token": token,
                },
            )

        response.raise_for_status()
        return response.json()

    except httpx.HTTPStatusError as exc:
        try:
            detalhe = exc.response.json()
        except ValueError:
            detalhe = "Erro retornado pela API de clientes."

        raise HTTPException(
            status_code=exc.response.status_code,
            detail=detalhe,
        )

    except httpx.RequestError:
        raise HTTPException(
            status_code=502,
            detail="Não foi possível conectar à API de clientes.",
        )


# ------NOVAS ROTAS DA DO DASHBOARD------------------


@router.post("/fechar-estado/{id_estado}")
async def fechar_estado(
    id_estado: int,
    current_user=Depends(get_current_active_user),
):

    api_url = os.getenv(
        "CLIENTES_API_URL",
        "http://host.docker.internal:8001",
    ).rstrip("/")

    api_key = os.getenv("CLIENTES_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="Chave de integração não configurada.",
        )

    token = gerar_token_integracao(current_user.id)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{api_url}/order/fechar-estado/{id_estado}",
                headers={
                    "X-API-Key": api_key,
                    "X-User-Token": token,
                },
            )

        response.raise_for_status()
        return response.json()

    except httpx.HTTPStatusError as exc:
        try:
            detalhe = exc.response.json()
        except ValueError:
            detalhe = "Erro retornado pela API de clientes."

        raise HTTPException(
            status_code=exc.response.status_code,
            detail=detalhe,
        )

    except httpx.RequestError:
        raise HTTPException(
            status_code=502,
            detail="Não foi possível conectar à API de clientes.",
        )


@router.post("/cancelar-venda/{id_client}/{id_venda}")
async def cancelar_venda(
    id_client: int,
    id_venda: int,
    current_user=Depends(get_current_active_user),
):

    api_url = os.getenv(
        "CLIENTES_API_URL",
        "http://host.docker.internal:8001",
    ).rstrip("/")

    api_key = os.getenv("CLIENTES_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="Chave de integração não configurada.",
        )

    token = gerar_token_integracao(current_user.id)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{api_url}/order/cancelar-venda/{id_client}/{id_venda}",
                headers={
                    "X-API-Key": api_key,
                    "X-User-Token": token,
                },
            )

        response.raise_for_status()
        return response.json()

    except httpx.HTTPStatusError as exc:
        try:
            detalhe = exc.response.json()
        except ValueError:
            detalhe = "Erro retornado pela API de clientes."

        raise HTTPException(
            status_code=exc.response.status_code,
            detail=detalhe,
        )

    except httpx.RequestError:
        raise HTTPException(
            status_code=502,
            detail="Não foi possível conectar à API de clientes.",
        )


@router.get("/dashboard-acompanhamento")
async def dashboard_acompanhamento(
    current_user=Depends(get_current_active_user),
):

    api_url = os.getenv(
        "CLIENTES_API_URL",
        "http://host.docker.internal:8001",
    ).rstrip("/")

    api_key = os.getenv("CLIENTES_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="Chave de integração não configurada.",
        )

    token = gerar_token_integracao(current_user.id)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{api_url}/order/dashboard-acompanhamento",
                headers={
                    "X-API-Key": api_key,
                    "X-User-Token": token,
                },
            )

        response.raise_for_status()
        return response.json()

    except httpx.HTTPStatusError as exc:
        try:
            detalhe = exc.response.json()
        except ValueError:
            detalhe = "Erro retornado pela API de clientes."

        raise HTTPException(
            status_code=exc.response.status_code,
            detail=detalhe,
        )

    except httpx.RequestError:
        raise HTTPException(
            status_code=502,
            detail="Não foi possível conectar à API de clientes.",
        )


# ROTAS PARA EDITAR CLIENTES -------------------------


@router.put("/editar-nome-cliente/{id_client}")
async def editar_nome_cliente(
    id_client: int,
    nome: str = Body(..., embed=True),
    current_user=Depends(get_current_active_user),
):
    api_url = os.getenv(
        "CLIENTES_API_URL",
        "http://host.docker.internal:8001",
    ).rstrip("/")

    api_key = os.getenv("CLIENTES_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="Chave de integração não configurada.",
        )

    token = gerar_token_integracao(current_user.id)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.put(
                f"{api_url}/order/editar-nome-cliente/{id_client}",
                headers={
                    "X-API-Key": api_key,
                    "X-User-Token": token,
                },
                json={"nome": nome},
            )

        response.raise_for_status()
        return response.json()

    except httpx.HTTPStatusError as exc:
        try:
            detalhe = exc.response.json()
        except ValueError:
            detalhe = "Erro retornado pela API de clientes."

        raise HTTPException(
            status_code=exc.response.status_code,
            detail=detalhe,
        )

    except httpx.RequestError:
        raise HTTPException(
            status_code=502,
            detail="Não foi possível conectar à API de clientes.",
        )


@router.put("/editar-telefone-cliente/{id_client}")
async def editar_telefone_cliente(
    id_client: int,
    telefone: str = Body(..., embed=True),
    current_user=Depends(get_current_active_user),
):
    api_url = os.getenv(
        "CLIENTES_API_URL",
        "http://host.docker.internal:8001",
    ).rstrip("/")

    api_key = os.getenv("CLIENTES_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="Chave de integração não configurada.",
        )

    token = gerar_token_integracao(current_user.id)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.put(
                f"{api_url}/order/editar-telefone-cliente/{id_client}",
                headers={
                    "X-API-Key": api_key,
                    "X-User-Token": token,
                },
                json={"telefone": telefone},
            )

        response.raise_for_status()
        return response.json()

    except httpx.HTTPStatusError as exc:
        try:
            detalhe = exc.response.json()
        except ValueError:
            detalhe = "Erro retornado pela API de clientes."

        raise HTTPException(
            status_code=exc.response.status_code,
            detail=detalhe,
        )

    except httpx.RequestError:
        raise HTTPException(
            status_code=502,
            detail="Não foi possível conectar à API de clientes.",
        )


@router.put("/ativar-cliente/{id_client}")
async def ativar_cliente(
    id_client: int,
    current_user=Depends(get_current_active_user),
):
    api_url = os.getenv(
        "CLIENTES_API_URL",
        "http://host.docker.internal:8001",
    ).rstrip("/")

    api_key = os.getenv("CLIENTES_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="Chave de integração não configurada.",
        )

    token = gerar_token_integracao(current_user.id)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.put(
                f"{api_url}/order/ativar-cliente/{id_client}",
                headers={
                    "X-API-Key": api_key,
                    "X-User-Token": token,
                },
            )

        response.raise_for_status()
        return response.json()

    except httpx.HTTPStatusError as exc:
        try:
            detalhe = exc.response.json()
        except ValueError:
            detalhe = "Erro retornado pela API de clientes."

        raise HTTPException(
            status_code=exc.response.status_code,
            detail=detalhe,
        )

    except httpx.RequestError:
        raise HTTPException(
            status_code=502,
            detail="Não foi possível conectar à API de clientes.",
        )


@router.put("/desativar-cliente/{id_client}")
async def desativar_cliente(
    id_client: int,
    current_user=Depends(get_current_active_user),
):
    api_url = os.getenv(
        "CLIENTES_API_URL",
        "http://host.docker.internal:8001",
    ).rstrip("/")

    api_key = os.getenv("CLIENTES_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="Chave de integração não configurada.",
        )

    token = gerar_token_integracao(current_user.id)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.put(
                f"{api_url}/order/desativar-cliente/{id_client}",
                headers={
                    "X-API-Key": api_key,
                    "X-User-Token": token,
                },
            )

        response.raise_for_status()
        return response.json()

    except httpx.HTTPStatusError as exc:
        try:
            detalhe = exc.response.json()
        except ValueError:
            detalhe = "Erro retornado pela API de clientes."

        raise HTTPException(
            status_code=exc.response.status_code,
            detail=detalhe,
        )

    except httpx.RequestError:
        raise HTTPException(
            status_code=502,
            detail="Não foi possível conectar à API de clientes.",
        )


@router.put("/editar-email-cliente/{id_client}")
async def editar_email_cliente(
    id_client: int,
    email: str = Body(..., embed=True),
    current_user=Depends(get_current_active_user),
):
    api_url = os.getenv(
        "CLIENTES_API_URL",
        "http://host.docker.internal:8001",
    ).rstrip("/")

    api_key = os.getenv("CLIENTES_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="Chave de integração não configurada.",
        )

    token = gerar_token_integracao(current_user.id)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.put(
                f"{api_url}/order/editar-email-cliente/{id_client}",
                headers={
                    "X-API-Key": api_key,
                    "X-User-Token": token,
                },
                json={"email": email},
            )

        response.raise_for_status()
        return response.json()

    except httpx.HTTPStatusError as exc:
        try:
            detalhe = exc.response.json()
        except ValueError:
            detalhe = "Erro retornado pela API de clientes."

        raise HTTPException(
            status_code=exc.response.status_code,
            detail=detalhe,
        )

    except httpx.RequestError:
        raise HTTPException(
            status_code=502,
            detail="Não foi possível conectar à API de clientes.",
        )
