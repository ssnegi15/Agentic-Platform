from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class AgentRunRequest(BaseModel):
    message: str = Field(min_length=1, max_length=32_000)
    session_id: str | None = Field(default=None, max_length=255)


class AgentRunResponse(BaseModel):
    trace_id: str
    message: str
    metadata: dict[str, Any]


class PrincipalResponse(BaseModel):
    subject: str
    username: str | None
    roles: list[str]
    groups: list[str]


class ModelPricingRequest(BaseModel):
    provider: str = Field(min_length=1, max_length=128)
    model: str = Field(min_length=1, max_length=255)
    input_cost_per_million: float = Field(ge=0)
    output_cost_per_million: float = Field(ge=0)
    effective_from: datetime
    effective_until: datetime | None = None

    @field_validator("effective_from", "effective_until")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("Pricing effective dates must include a timezone.")
        return value


class ModelPricingResponse(ModelPricingRequest):
    id: UUID
