from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_platform.models import ModelPricing


@dataclass(frozen=True)
class EstimatedCost:
    input_cost: float | None
    output_cost: float | None
    total_cost: float | None
    estimated: bool = True


async def estimate_cost(
    session: AsyncSession,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    at: datetime,
) -> EstimatedCost:
    pricing = await session.scalar(
        select(ModelPricing)
        .where(
            ModelPricing.provider == provider,
            ModelPricing.model == model,
            ModelPricing.effective_from <= at,
            (ModelPricing.effective_until.is_(None) | (ModelPricing.effective_until > at)),
        )
        .order_by(ModelPricing.effective_from.desc())
        .limit(1)
    )
    if pricing is None:
        return EstimatedCost(None, None, None)

    input_cost = input_tokens * pricing.input_cost_per_million / 1_000_000
    output_cost = output_tokens * pricing.output_cost_per_million / 1_000_000
    return EstimatedCost(input_cost, output_cost, input_cost + output_cost)
