from pathlib import Path

ROOT = Path(__file__).resolve().parent

FILES = {
    "README.md": """\
# Agentic Platform

Open-source GitHub-first AI agent platform.

## Stack

- Python 3.13
- FastAPI
- PostgreSQL
- pgvector
- Keycloak/OIDC
- Vendor-neutral LLM providers
- PostgreSQL telemetry
- Evaluation framework
- Dashboard

No Azure AI Foundry, Firebase Auth, Ollama, Jaeger, Langfuse,
LangSmith, Redis, Kafka, Kubernetes, or Docker Compose is required.
""",

    ".gitignore": """\
.env
.env.*
!.env.example
.venv/
__pycache__/
*.py[cod]
*.egg-info/
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
node_modules/
.next/
dist/
build/
""",

    ".env.example": """\
APP_NAME=agent-platform
ENVIRONMENT=development
APPLICATION_VERSION=0.1.0

DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/agent_platform

OIDC_ISSUER_URL=
OIDC_AUDIENCE=
OIDC_CLIENT_ID=

LLM_PROVIDER=openai-compatible
LLM_BASE_URL=
LLM_API_KEY=
LLM_DEFAULT_MODEL=

TELEMETRY_ENABLED=true
TELEMETRY_CAPTURE_INPUTS=false
TELEMETRY_CAPTURE_OUTPUTS=false
""",

    ".python-version": "3.13\n",

    "pyproject.toml": """\
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "agent-platform"
version = "0.1.0"
description = "Open-source GitHub-first AI agent platform"
readme = "README.md"
requires-python = ">=3.13,<3.14"

dependencies = [
    "fastapi>=0.141,<1",
    "uvicorn[standard]>=0.35,<1",
    "pydantic>=2.11,<3",
    "pydantic-settings>=2.10,<3",
    "sqlalchemy[asyncio]>=2,<3",
    "psycopg[binary]>=3.2,<4",
    "alembic>=1.16,<2",
    "pgvector>=0.4,<1",
    "httpx>=0.28,<1",
    "PyJWT[crypto]>=2.10,<3",
    "openai>=2,<3",
]

[dependency-groups]
dev = [
    "pytest>=8,<10",
    "pytest-asyncio>=1,<2",
    "pytest-cov>=6,<8",
    "ruff>=0.14,<1",
    "mypy>=1.18,<2",
]

[tool.hatch.build.targets.wheel]
packages = ["src/agent_platform"]

[tool.ruff]
line-length = 100
target-version = "py313"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "SIM"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"

[tool.mypy]
python_version = "3.13"
strict = true
""",

    "src/agent_platform/__init__.py": """\
__version__ = "0.1.0"
""",

    "src/agent_platform/api/__init__.py": "",

    "src/agent_platform/api/main.py": """\
from fastapi import FastAPI

from agent_platform import __version__

app = FastAPI(
    title="Agentic Platform",
    version=__version__,
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "version": __version__,
    }


@app.get("/ready")
async def ready() -> dict[str, str]:
    return {"status": "ready"}


@app.get("/api/v1")
async def api_info() -> dict[str, str]:
    return {
        "name": "agent-platform",
        "version": __version__,
    }
""",

    "src/agent_platform/config/__init__.py": "",

    "src/agent_platform/config/settings.py": """\
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "agent-platform"
    environment: str = "development"
    application_version: str = "0.1.0"

    database_url: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/agent_platform"
    )

    oidc_issuer_url: str | None = None
    oidc_audience: str | None = None
    oidc_client_id: str | None = None

    llm_provider: str = "openai-compatible"
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_default_model: str | None = None

    telemetry_enabled: bool = True
    telemetry_capture_inputs: bool = False
    telemetry_capture_outputs: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
""",

    "src/agent_platform/agents/__init__.py": "",

    "src/agent_platform/agents/runtime.py": """\
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentRequest:
    message: str
    user_id: str | None = None
    session_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResponse:
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)


class Agent:
    name = "default"

    async def run(
        self,
        request: AgentRequest,
    ) -> AgentResponse:
        return AgentResponse(
            message="Agent runtime ready.",
            metadata={
                "agent": self.name,
                "session_id": request.session_id,
            },
        )
""",

    "src/agent_platform/llm/__init__.py": """\
from .base import (
    LLMMessage,
    LLMProvider,
    LLMRequest,
    LLMResponse,
    TokenUsage,
)

__all__ = [
    "LLMMessage",
    "LLMProvider",
    "LLMRequest",
    "LLMResponse",
    "TokenUsage",
]
""",

    "src/agent_platform/llm/base.py": """\
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class LLMMessage:
    role: str
    content: str


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class LLMRequest:
    model: str
    messages: list[LLMMessage]
    temperature: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMResponse:
    model: str
    content: str
    usage: TokenUsage
    latency_ms: float
    estimated_cost: float | None = None


class LLMProvider(Protocol):
    async def complete(
        self,
        request: LLMRequest,
    ) -> LLMResponse:
        ...
""",

    "src/agent_platform/telemetry/__init__.py": """\
from .base import Span, Telemetry, Trace

__all__ = ["Span", "Telemetry", "Trace"]
""",

    "src/agent_platform/telemetry/base.py": """\
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol


@dataclass
class Trace:
    trace_id: str
    user_id: str | None
    session_id: str | None
    agent: str
    workflow: str | None
    environment: str
    application_version: str
    started_at: datetime
    ended_at: datetime | None = None
    status: str = "running"
    error: str | None = None


@dataclass
class Span:
    span_id: str
    trace_id: str
    parent_span_id: str | None
    span_type: str
    name: str
    started_at: datetime
    ended_at: datetime | None = None
    status: str = "running"
    metadata: dict[str, Any] = field(default_factory=dict)


class Telemetry(Protocol):
    async def start_trace(self, trace: Trace) -> None:
        ...

    async def finish_trace(
        self,
        trace_id: str,
        status: str,
        error: str | None = None,
    ) -> None:
        ...

    async def record_span(self, span: Span) -> None:
        ...
""",

    "src/agent_platform/telemetry/memory.py": """\
from agent_platform.telemetry.base import Span, Trace


class InMemoryTelemetry:
    def __init__(self) -> None:
        self.traces: dict[str, Trace] = {}
        self.spans: list[Span] = []

    async def start_trace(self, trace: Trace) -> None:
        self.traces[trace.trace_id] = trace

    async def finish_trace(
        self,
        trace_id: str,
        status: str,
        error: str | None = None,
    ) -> None:
        trace = self.traces[trace_id]
        trace.status = status
        trace.error = error

    async def record_span(self, span: Span) -> None:
        self.spans.append(span)
""",

    "src/agent_platform/pricing/__init__.py": "",

    "src/agent_platform/pricing/models.py": """\
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ModelPricing:
    provider: str
    model: str
    input_cost_per_1m_tokens: float
    output_cost_per_1m_tokens: float
    effective_from: datetime
    effective_until: datetime | None = None


def estimate_cost(
    pricing: ModelPricing,
    input_tokens: int,
    output_tokens: int,
) -> float:
    return (
        input_tokens / 1_000_000
    ) * pricing.input_cost_per_1m_tokens + (
        output_tokens / 1_000_000
    ) * pricing.output_cost_per_1m_tokens
""",

    "src/agent_platform/evaluations/__init__.py": "",

    "src/agent_platform/evaluations/base.py": """\
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class EvaluationCase:
    case_id: str
    input: Any
    expected_output: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvaluationResult:
    evaluator: str
    score: float
    passed: bool
    reason: str | None = None


class Evaluator(Protocol):
    name: str

    async def evaluate(
        self,
        case: EvaluationCase,
        actual_output: Any,
    ) -> EvaluationResult:
        ...
""",

    "src/agent_platform/evaluations/deterministic.py": """\
from agent_platform.evaluations.base import (
    EvaluationCase,
    EvaluationResult,
)


class ExactMatchEvaluator:
    name = "exact_match"

    async def evaluate(
        self,
        case: EvaluationCase,
        actual_output: object,
    ) -> EvaluationResult:
        passed = actual_output == case.expected_output

        return EvaluationResult(
            evaluator=self.name,
            score=1.0 if passed else 0.0,
            passed=passed,
            reason=None if passed else "Output mismatch.",
        )
""",

    "src/agent_platform/evaluations/runner.py": """\
import asyncio

from agent_platform.evaluations.base import EvaluationCase
from agent_platform.evaluations.deterministic import ExactMatchEvaluator


async def run() -> bool:
    case = EvaluationCase(
        case_id="smoke-001",
        input="hello",
        expected_output="hello",
    )

    result = await ExactMatchEvaluator().evaluate(
        case,
        "hello",
    )

    return result.passed


if __name__ == "__main__":
    passed = asyncio.run(run())
    print("[eval] PASSED" if passed else "[eval] FAILED")
    raise SystemExit(0 if passed else 1)
""",

    "src/agent_platform/auth/__init__.py": "",

    "src/agent_platform/auth/oidc.py": """\
from dataclasses import dataclass


@dataclass(frozen=True)
class AuthenticatedUser:
    subject: str
    email: str | None = None
    name: str | None = None
    roles: tuple[str, ...] = ()
    groups: tuple[str, ...] = ()


class OIDCAuthenticator:
    async def authenticate(
        self,
        token: str,
    ) -> AuthenticatedUser:
        raise NotImplementedError(
            "Configure Keycloak/OIDC before authentication."
        )
""",

    "src/agent_platform/tools/__init__.py": "",

    "src/agent_platform/tools/base.py": """\
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class ToolResult:
    output: Any
    success: bool
    error: str | None = None


class Tool(Protocol):
    name: str

    async def execute(
        self,
        arguments: dict[str, Any],
    ) -> ToolResult:
        ...
""",

    "src/agent_platform/db/__init__.py": "",

    "src/agent_platform/db/models/__init__.py": "",

    "src/agent_platform/db/session.py": """\
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from agent_platform.config.settings import get_settings


engine = create_async_engine(
    get_settings().database_url,
    pool_pre_ping=True,
)

SessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
""",

    "tests/__init__.py": "",

    "tests/unit/test_health.py": """\
from fastapi.testclient import TestClient

from agent_platform.api.main import app


def test_health() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ready() -> None:
    response = TestClient(app).get("/ready")

    assert response.status_code == 200
""",

    "tests/unit/test_llm.py": """\
from agent_platform.llm.base import TokenUsage


def test_tokens() -> None:
    usage = TokenUsage(
        input_tokens=10,
        output_tokens=20,
    )

    assert usage.total_tokens == 30
""",

    "tests/unit/test_pricing.py": """\
from datetime import datetime, timezone

from agent_platform.pricing.models import (
    ModelPricing,
    estimate_cost,
)


def test_cost() -> None:
    pricing = ModelPricing(
        provider="test",
        model="test",
        input_cost_per_1m_tokens=1.0,
        output_cost_per_1m_tokens=2.0,
        effective_from=datetime.now(timezone.utc),
    )

    assert estimate_cost(
        pricing,
        1_000_000,
        1_000_000,
    ) == 3.0
""",

    "tests/unit/test_evaluation.py": """\
import asyncio

from agent_platform.evaluations.base import EvaluationCase
from agent_platform.evaluations.deterministic import ExactMatchEvaluator


def test_evaluation() -> None:
    case = EvaluationCase(
        case_id="1",
        input="hello",
        expected_output="hello",
    )

    result = asyncio.run(
        ExactMatchEvaluator().evaluate(
            case,
            "hello",
        )
    )

    assert result.passed
""",

    "evals/datasets/smoke.json": """\
{
  "name": "smoke",
  "version": "1",
  "cases": [
    {
      "id": "smoke-001",
      "input": "hello",
      "expected_output": "hello"
    }
  ]
}
""",

    "migrations/README.md": "# PostgreSQL migrations.\n",

    "migrations/versions/.gitkeep": "",

    "docs/architecture.md": """\
# Architecture

GitHub
-> GitHub Actions
-> FastAPI
-> Agent Runtime
-> LLM Provider / Tools
-> PostgreSQL + pgvector
-> Telemetry
-> Evaluations
-> Dashboard

Keycloak provides OIDC authentication.

All LLM, telemetry and evaluation functionality uses replaceable
application interfaces.
""",

    "docs/telemetry.md": """\
# Telemetry

Tracks traces, spans, agent steps, LLM calls, tool calls,
tokens, latency, estimated costs and errors.

Initial storage backend: PostgreSQL.
""",

    "docs/evaluations.md": """\
# Evaluations

Evaluator types:

- deterministic
- reference-based
- LLM-as-judge

Results are designed for PostgreSQL persistence and CI quality gates.
""",

    "apps/dashboard/README.md": """\
# Dashboard

Dashboard for system metrics, traces, agents, models,
tokens, estimated costs, tools and evaluations.
""",
}


def write_file(relative_path: str, content: str) -> None:
    path = ROOT / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.lstrip(), encoding="utf-8")
    print(f"[created] {relative_path}")


def main() -> None:
    print("=== Agentic Platform Bootstrap ===")
    print(f"Repository: {ROOT}")

    for relative_path, content in FILES.items():
        write_file(relative_path, content)

    for directory in (
        "tests/integration",
        "tests/fixtures",
        "migrations/versions",
        "apps/dashboard",
    ):
        (ROOT / directory).mkdir(parents=True, exist_ok=True)

    print()
    print("=== COMPLETE ===")
    print(f"Generated project in: {ROOT}")


if __name__ == "__main__":
    main()
