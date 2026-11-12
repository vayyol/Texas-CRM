"""
Plan helpers: resolve the user's current plan and plan-based limits.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subscription import Subscription

# Maximum number of clients a user on the free plan can register.
FREE_CLIENT_LIMIT = 5


async def get_user_plan(db: AsyncSession, user_id: uuid.UUID) -> str:
    """Return the user's active plan name (``free`` when there is none)."""
    result = await db.execute(
        select(Subscription.plan_name).where(
            Subscription.user_id == user_id,
            Subscription.status.in_(["active", "trialing"]),
        )
    )
    plans = set(result.scalars().all())
    return next((plan for plan in plans if plan != "free"), "free")
