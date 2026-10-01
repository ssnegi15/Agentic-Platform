#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


FILES = {
    ".gitignore": """
.env
.env.*
!.env.example
.venv/
__pycache__/
*.py[cod]
*.egg-info/
.pytest_cache/
.coverage
.mypy_cache/
.ruff_cache/
build/
dist/
node_modules/
.next/
.DS_Store
""",

    ".python-version": "3.13\n",

    ".env.example": """
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

    "pyproject.toml": """
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
    "structlog>=25,<26",
]

[dependency-groups]
dev = [
    "pytest>=8,<10",
    "pytest-asyncio>=1,<2",
    "pytest-cov>=6,<8",
    "ruff>=0.14,<1",
    "mypy>=1.18,<2",
    "pip-audit>=2.9,<3",
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

    "README.md": """
# AI Agent Platform

GitHub-first, open-source AI agent platform.

## Architecture

- FastAPI
- Plain Python agents
- PostgreSQL
- pgvector
- Keycloak / OIDC
- Vendor-neutral LLM abstraction
- PostgreSQL telemetry
- Evaluation framework
- GitHub Actions

The platform does not require:

- Azure AI Foundry
- Firebase Auth
- Ollama
- Jaeger
- Langfuse
- LangSmith
- Redis
- Kafka
- Kubernetes
- Docker Compose

## Bootstrap

Run:

    python scripts/bootstrap.py

The bootstrap process does not require application secrets.
""",

    "src/agent_platform/__init__.py": """
__version__ = "0.1.0"
""",

    "src/agent_platform/config/__init__.py": "",

    "src/agent_platform/config/settings.py": """
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "agent-platform"
    environment: str = "development"
    application_version: str = "0.1.0"

    database_url: str = (
        "postgresql+psycopg://postgres:postgres"
        "@localhost:5432/agent_platform"
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
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
""",

    "src/agent_platform/api/__init__.py": "",

    "src/agent_platform/api/main.py": """
from fastapi import FastAPI

from agent_platform import __version__
from agent_platform.config.settings import get_settings


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
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
    return {
        "status": "ready",
    }
""",

    "src/agent_platform/agents/__init__.py": "",

    "src/agent_platform/agents/runtime.py": """
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
            metadata={"agent": self.name},
        )
""",

    "src/agent_platform/llm/__init__.py": "",

    "src/agent_platform/llm/base.py": """
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
    metadata: dict[str, Any] = field(default_factory=dict)


class LLMProvider(Protocol):
    async def complete(
        self,
        request: LLMRequest,
    ) -> LLMResponse:
        ...
""",

    "src/agent_platform/telemetry/__init__.py": """
from agent_platform.telemetry.base import Span, Telemetry, Trace

__all__ = ["Span", "Telemetry", "Trace"]
""",

    "src/agent_platform/telemetry/base.py": """
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

    "src/agent_platform/evaluations/base.py": """
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

    "src/agent_platform/evaluations/runner.py": """
def main() -> int:
    print("Evaluation framework ready; no datasets configured.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
""",

    "src/agent_platform/pricing/__init__.py": "",

    "src/agent_platform/pricing/models.py": """
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
    input_cost = (
        input_tokens / 1_000_000
    ) * pricing.input_cost_per_1m_tokens

    output_cost = (
        output_tokens / 1_000_000
    ) * pricing.output_cost_per_1m_tokens

    return input_cost + output_cost
""",

    "src/agent_platform/db/__init__.py": "",
    "src/agent_platform/db/models/__init__.py": "",

    "tests/unit/test_health.py": """
from fastapi.testclient import TestClient

from agent_platform.api.main import app


def test_health() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
""",

    "tests/unit/test_llm.py": """
from agent_platform.llm.base import TokenUsage


def test_token_usage() -> None:
    usage = TokenUsage(
        input_tokens=10,
        output_tokens=20,
    )

    assert usage.total_tokens == 30
""",

    "tests/unit/test_evaluations.py": """
from agent_platform.evaluations.base import EvaluationCase


def test_evaluation_case() -> None:
    case = EvaluationCase(
        case_id="case-1",
        input="hello",
    )

    assert case.case_id == "case-1"
""",

    ".github/workflows/ci.yml": """
name: CI

on:
  push:
    branches:
      - main
  pull_request:
  workflow_dispatch:

permissions:
  contents: read

jobs:
  ci:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v6

      - name: Setup Python
        uses: actions/setup-python@v6
        with:
          python-version: "3.13"

      - name: Setup uv
        uses: astral-sh/setup-uv@v7
        with:
          enable-cache: true

      - name: Run bootstrap
        run: python scripts/bootstrap.py
""",
}


DIRECTORIES = [
    ".github/workflows",
    "docs",
    "evals/datasets",
    "evals/evaluators",
    "evals/baselines",
    "migrations/versions",
    "apps/dashboard",
    "src/agent_platform/api",
    "src/agent_platform/agents",
    "src/agent_platform/auth",
    "src/agent_platform/config",
    "src/agent_platform/db/models",
    "src/agent_platform/evaluations",
    "src/agent_platform/llm",
    "src/agent_platform/pricing",
    "src/agent_platform/telemetry",
    "src/agent_platform/tools",
    "tests/unit",
    "tests/integration",
    "tests/fixtures",
]


def create_repository() -> None:
    print("\n[bootstrap] Creating repository...\n")

    for directory in DIRECTORIES:
        (ROOT / directory).mkdir(
            parents=True,
            exist_ok=True,
        )

    for filename, content in FILES.items():
        path = ROOT / filename

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        if not path.exists():
            path.write_text(
                content.lstrip(),
                encoding="utf-8",
            )
            print(f"[created] {filename}")

    print("\n[bootstrap] Repository created.\n")


def require(command: str) -> None:
    if shutil.which(command) is None:
        print(f"[error] Missing required command: {command}")
        raise SystemExit(1)


def run(command: list[str]) -> None:
    print("$ " + " ".join(command))

    result = subprocess.run(
        command,
        cwd=ROOT,
        check=False,
    )

    if result.returncode != 0:
        raise SystemExit(result.returncode)


def check() -> None:
    if sys.version_info < (3, 13) or sys.version_info >= (3, 14):
        print("[error] Python 3.13 is required.")
        raise SystemExit(1)

    require("git")
    require("uv")

    required = [
        "pyproject.toml",
        "README.md",
        ".env.example",
        ".github/workflows/ci.yml",
    ]

    for filename in required:
        if not (ROOT / filename).exists():
            print(f"[error] Missing: {filename}")
            raise SystemExit(1)

    print("[ok] Environment ready.")


def install() -> None:
    require("uv")
    run(["uv", "sync"])


def format_check() -> None:
    run(
        [
            "uv",
            "run",
            "ruff",
            "format",
            ".",
        ]
    )


def lint() -> None:
    # Automatically fix safe Ruff issues first.
    run(
        [
            "uv",
            "run",
            "ruff",
            "check",
            ".",
            "--fix",
        ]
    )

    # Then verify that nothing remains.
    run(
        [
            "uv",
            "run",
            "ruff",
            "check",
            ".",
        ]
    )



def typecheck() -> None:
    run(
        [
            "uv",
            "run",
            "mypy",
            "src",
        ]
    )


def security() -> None:
    run(
        [
            "uv",
            "run",
            "pip-audit",
        ]
    )


def test() -> None:
    run(
        [
            "uv",
            "run",
            "pytest",
            "-v",
            "--cov=src",
        ]
    )


def evaluate() -> None:
    run(
        [
            "uv",
            "run",
            "python",
            "-m",
            "agent_platform.evaluations.runner",
        ]
    )


def migrate() -> None:
    if not os.getenv("DATABASE_URL"):
        print("[skip] DATABASE_URL not configured.")
        return

    print("[info] Database migration support will be enabled with "
          "the PostgreSQL migration layer.")

    return


def all_checks() -> None:
    create_repository()
    check()
    install()

    format_check()
    lint()
    typecheck()
    security()
    test()
    evaluate()
    migrate()

    print()
    print("========================================")
    print(" AI AGENT PLATFORM BOOTSTRAP COMPLETE")
    print("========================================")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="AI Agent Platform bootstrap script",
    )

    parser.add_argument(
        "command",
        nargs="?",
        default="all",
        choices=[
            "all",
            "init",
            "check",
            "install",
            "test",
            "lint",
            "format",
            "typecheck",
            "security",
            "eval",
            "migrate",
        ],
    )

    args = parser.parse_args()

    if args.command == "init":
        create_repository()

    elif args.command == "check":
        check()

    elif args.command == "install":
        install()

    elif args.command == "test":
        test()

    elif args.command == "lint":
        lint()

    elif args.command == "format":
        format_check()

    elif args.command == "typecheck":
        typecheck()

    elif args.command == "security":
        security()

    elif args.command == "eval":
        evaluate()

    elif args.command == "migrate":
        migrate()

    else:
        all_checks()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
