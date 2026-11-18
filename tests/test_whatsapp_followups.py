from datetime import datetime, timedelta, timezone

from app.services.whatsapp_followups import (
    LOCAL_TZ,
    _build_candidates,
    _render_message,
    normalize_phone,
)


def test_all_four_followup_types_are_detected():
    now = datetime.now(timezone.utc)
    today = datetime.now(LOCAL_TZ).date().isoformat()
    clients = [
        {
            "id": 12,
            "nome": "Maria",
            "telefone": "(73) 99999-1234",
            "estados": [
                {
                    "id": 101,
                    "tipo": "VENDA_REALIZADA",
                    "status": "FECHADO",
                    "descricao": "Camisa",
                    "valor_total": 150,
                    "created_at": (now - timedelta(minutes=2)).isoformat(),
                },
                {
                    "id": 102,
                    "tipo": "VENDA_NAO_REALIZADA",
                    "status": "FECHADO",
                    "descricao": "Calça",
                    "valor_total": 90,
                    "created_at": (now - timedelta(days=6)).isoformat(),
                },
                {
                    "id": 103,
                    "tipo": "PROPOSTA",
                    "status": "ABERTO",
                    "descricao": "Orçamento de uniforme",
                    "valor_total": 300,
                    "created_at": (now - timedelta(days=2)).isoformat(),
                },
            ],
        }
    ]
    payments = [
        {
            "id_venda": 101,
            "client_id": 12,
            "nome": "Maria",
            "telefone": "(73) 99999-1234",
            "descricao": "Camisa",
            "proxima_parcela": 2,
            "valor_parcela": 75,
            "data_vencimento": today,
        }
    ]

    candidates = _build_candidates(
        clients,
        payments,
        now - timedelta(days=10),
        now,
    )

    assert {item["followup_type"] for item in candidates} == {
        "sale_completed",
        "installment_overdue",
        "sale_lost",
        "proposal_no_reply",
    }
    assert len(candidates) == 4


def test_open_proposal_only_triggers_after_one_day_and_closed_is_ignored():
    now = datetime.now(timezone.utc)
    clients = [{
        "id": 1,
        "nome": "Cliente",
        "telefone": "73999991234",
        "estados": [
            {
                "id": 1,
                "tipo": "PROPOSTA",
                "status": "ABERTO",
                "created_at": (now - timedelta(hours=12)).isoformat(),
            },
            {
                "id": 2,
                "tipo": "PROPOSTA",
                "status": "FECHADO",
                "created_at": (now - timedelta(days=3)).isoformat(),
            },
        ],
    }]

    candidates = _build_candidates(clients, [], now - timedelta(days=5), now)

    assert candidates == []


def test_message_variables_and_phone_normalization():
    message = _render_message("Olá {nome}, valor {valor_venda}", {
        "nome": "Ana",
        "valor_venda": "R$ 25,00",
    })

    assert message == "Olá Ana, valor R$ 25,00"
    assert normalize_phone("(73) 99999-1234") == "5573999991234"
    assert normalize_phone("invalid") is None



def test_overdue_installment_is_found_even_when_due_date_precedes_last_scan():
    now = datetime.now(timezone.utc)
    today = datetime.now(LOCAL_TZ).date().isoformat()
    payments = [{
        "id_venda": 77,
        "client_id": 9,
        "nome": "João",
        "telefone": "73999991234",
        "descricao": "Serviço",
        "proxima_parcela": 1,
        "valor_parcela": 120,
        "data_vencimento": today,
    }]

    candidates = _build_candidates([], payments, now - timedelta(minutes=5), now)

    assert len(candidates) == 1
    assert candidates[0]["followup_type"] == "installment_overdue"
