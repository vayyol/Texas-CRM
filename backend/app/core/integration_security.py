import os
import time

import jwt


def gerar_token_integracao(user_id) -> str:
    agora = int(time.time())
    secret = os.getenv("INTEGRATION_SECRET")

    if not secret:
        raise RuntimeError("INTEGRATION_SECRET não configurado.")

    return jwt.encode(
        {
            "sub": str(user_id),
            "iat": agora,
            "exp": agora + 60,
            "iss": "saas-starter-kit",
            "aud": "clientes-api",
        },
        secret,
        algorithm="HS256",
    )
