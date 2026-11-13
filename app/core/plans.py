"""
Plan helpers: resolve the user's current plan and plan-based limits.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subscription import Subscription

# Maximum number of clients a user on the free plan can register.
FREE_CLIENT_LIMIT = 5


async def get_user_plan(db: AsyncSession, user_id: uuid.UUID) -> str:
    """Return the user's active plan name (``free`` when there is none).

    Conta como ativa a assinatura ``active``/``trialing`` e também a ``canceled`` que ainda está
    dentro do período já pago (o cancelamento para as cobranças, mas o acesso vai até o fim do ciclo).
    """
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Subscription.plan_name).where(
            Subscription.user_id == user_id,
            or_(
                Subscription.status.in_(["active", "trialing"]),
                and_(Subscription.status == "canceled", Subscription.current_period_end > now),
            ),
        )
    )
    plans = set(result.scalars().all())
    return next((plan for plan in plans if plan != "free"), "free")
