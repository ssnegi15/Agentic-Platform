from pathlib import Path

ROOT = Path(__file__).resolve().parent


def write(path: str, content: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    print(f"[created] {target}")


def main() -> None:
    print(f"[bootstrap] root = {ROOT}")

    files = {
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

        "README.md": """\
# Agentic Platform

Open-source GitHub-first AI agent platform.

Architecture:

- FastAPI
- Plain Python agents
- PostgreSQL
- pgvector
- Keycloak/OIDC
- Vendor-neutral LLM providers
- PostgreSQL telemetry
- Evaluation framework
- Dashboard
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

        "src/agent_platform/llm/__init__.py": "",

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

        "src/agent_platform/telemetry/__init__.py": "",
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

        "tests/__init__.py": "",
        "tests/unit/test_health.py": """\
from fastapi.testclient import TestClient

from agent_platform.api.main import app


def test_health() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
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

        "docs/architecture.md": """\
# Architecture

GitHub Actions
-> FastAPI
-> Agent Runtime
-> LLM Provider / Tools
-> PostgreSQL + pgvector
-> Telemetry
-> Evaluations
-> Dashboard

Keycloak/OIDC provides authentication.

LLM, telemetry and evaluation layers use replaceable interfaces.
""",

        "migrations/README.md": "# PostgreSQL migrations.\n",

        "apps/dashboard/README.md": """\
# Dashboard

Future dashboard for telemetry, costs, agents, tools,
LLM usage, traces and evaluations.
""",
    }

    for path, content in files.items():
        write(path, content)

    print()
    print("[bootstrap] SUCCESS")
    print(f"[bootstrap] pyproject.toml = {(ROOT / 'pyproject.toml').exists()}")
    print(f"[bootstrap] src = {(ROOT / 'src/agent_platform').exists()}")


if __name__ == "__main__":
    main()
