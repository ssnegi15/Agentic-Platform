#!/usr/bin/env python3
"""
AI Agent Platform - single project bootstrap/management script.

Usage:

    python scripts/bootstrap.py check
    python scripts/bootstrap.py install
    python scripts/bootstrap.py migrate
    python scripts/bootstrap.py test
    python scripts/bootstrap.py eval
    python scripts/bootstrap.py seed
    python scripts/bootstrap.py all

The same commands are used locally and by GitHub Actions.

This script does NOT start infrastructure.

PostgreSQL, Keycloak, and an LLM provider are external services.
The application only verifies/configures what it needs to use them.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def log(message: str) -> None:
    print(f"[bootstrap] {message}")


def success(message: str) -> None:
    print(f"\033[32m[ok]\033[0m {message}")


def warning(message: str) -> None:
    print(f"\033[33m[warning]\033[0m {message}")


def error(message: str) -> None:
    print(f"\033[31m[error]\033[0m {message}")


def command_exists(command: str) -> bool:
    return shutil.which(command) is not None


def run(
    command: list[str],
    *,
    check: bool = True,
    env: dict[str, str] | None = None,
) -> int:
    log("$ " + " ".join(command))

    result = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        check=False,
    )

    if check and result.returncode != 0:
        raise SystemExit(result.returncode)

    return result.returncode


def require_command(command: str, installation_hint: str) -> None:
    if not command_exists(command):
        error(f"'{command}' is not installed.")
        error(installation_hint)
        raise SystemExit(1)


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

def check_python() -> None:
    version = sys.version_info

    if version < (3, 13) or version >= (3, 14):
        error(
            f"Python {version.major}.{version.minor} detected. "
            "Python 3.13 is required."
        )
        raise SystemExit(1)

    success(f"Python {version.major}.{version.minor}")


def check_required_files() -> None:
    required = [
        "pyproject.toml",
        "README.md",
        ".env.example",
        "scripts/bootstrap.py",
    ]

    missing = [
        path
        for path in required
        if not (ROOT / path).exists()
    ]

    if missing:
        for path in missing:
            error(f"Missing: {path}")
        raise SystemExit(1)

    success("Required project files exist")


def check_environment() -> None:
    log("Checking development environment...")

    check_python()

    require_command(
        "git",
        "Install Git from https://git-scm.com/",
    )

    require_command(
        "uv",
        "Install uv from https://docs.astral.sh/uv/",
    )

    check_required_files()

    if not (ROOT / ".env").exists():
        warning(
            ".env does not exist. "
            "Copy .env.example to .env and configure it."
        )

    success("Environment check complete")


# ---------------------------------------------------------------------------
# Dependency management
# ---------------------------------------------------------------------------

def install() -> None:
    require_command(
        "uv",
        "Install uv from https://docs.astral.sh/uv/",
    )

    log("Installing Python dependencies...")

    run(["uv", "sync"])

    success("Dependencies installed")


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def database_url() -> str:
    url = os.getenv("DATABASE_URL")

    if not url:
        env_file = ROOT / ".env"

        if env_file.exists():
            for line in env_file.read_text().splitlines():
                line = line.strip()

                if not line or line.startswith("#"):
                    continue

                if line.startswith("DATABASE_URL="):
                    url = line.split("=", 1)[1].strip()
                    break

    if not url:
        warning(
            "DATABASE_URL is not configured. "
            "Database operations may fail."
        )
        return ""

    return url


def migrate() -> None:
    log("Running database migrations...")

    database_url()

    if not (ROOT / "alembic.ini").exists():
        warning(
            "alembic.ini does not exist yet. "
            "Database migrations will be enabled when the migration layer "
            "is added."
        )
        return

    run(
        [
            "uv",
            "run",
            "alembic",
            "upgrade",
            "head",
        ]
    )

    success("Database migrations complete")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test() -> None:
    log("Running test suite...")

    run(
        [
            "uv",
            "run",
            "pytest",
            "-v",
            "--cov=src",
            "--cov-report=term-missing",
        ]
    )

    success("Tests passed")


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def evaluate() -> None:
    log("Running evaluation suite...")

    evaluation_runner = (
        ROOT
        / "src"
        / "agent_platform"
        / "evaluations"
        / "runner.py"
    )

    if not evaluation_runner.exists():
        warning(
            "Evaluation runner does not exist yet. "
            "Evaluation infrastructure will be enabled when implemented."
        )
        return

    run(
        [
            "uv",
            "run",
            "python",
            "-m",
            "agent_platform.evaluations.runner",
        ]
    )

    success("Evaluations passed")


# ---------------------------------------------------------------------------
# Seed
# ---------------------------------------------------------------------------

def seed() -> None:
    log("Seeding development data...")

    seed_module = (
        ROOT
        / "src"
        / "agent_platform"
        / "db"
        / "seed.py"
    )

    if not seed_module.exists():
        warning(
            "Database seed module does not exist yet. "
            "Skipping seed operation."
        )
        return

    run(
        [
            "uv",
            "run",
            "python",
            "-m",
            "agent_platform.db.seed",
        ]
    )

    success("Database seed complete")


# ---------------------------------------------------------------------------
# Quality checks
# ---------------------------------------------------------------------------

def lint() -> None:
    log("Running Ruff...")

    run(
        [
            "uv",
            "run",
            "ruff",
            "check",
            ".",
        ]
    )

    success("Lint passed")


def format_check() -> None:
    log("Checking formatting...")

    run(
        [
            "uv",
            "run",
            "ruff",
            "format",
            "--check",
            ".",
        ]
    )

    success("Formatting check passed")


def type_check() -> None:
    log("Running mypy...")

    run(
        [
            "uv",
            "run",
            "mypy",
            "src",
        ]
    )

    success("Type checking passed")


def security_check() -> None:
    log("Running dependency security audit...")

    run(
        [
            "uv",
            "run",
            "pip-audit",
        ]
    )

    success("Security audit passed")


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------

def all_checks() -> None:
    """
    Canonical CI/deployment quality pipeline.

    This is intentionally deterministic and does not start infrastructure.
    """

    log("Running complete project pipeline")

    check_environment()

    install()

    format_check()

    lint()

    type_check()

    security_check()

    test()

    evaluate()

    log("Complete pipeline passed")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="AI Agent Platform project bootstrapper",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    subparsers.add_parser(
        "check",
        help="Check local/CI environment.",
    )

    subparsers.add_parser(
        "install",
        help="Install Python dependencies.",
    )

    subparsers.add_parser(
        "migrate",
        help="Run PostgreSQL/Alembic migrations.",
    )

    subparsers.add_parser(
        "test",
        help="Run tests.",
    )

    subparsers.add_parser(
        "eval",
        help="Run agent evaluations.",
    )

    subparsers.add_parser(
        "seed",
        help="Seed development data.",
    )

    subparsers.add_parser(
        "lint",
        help="Run linting.",
    )

    subparsers.add_parser(
        "format",
        help="Check formatting.",
    )

    subparsers.add_parser(
        "typecheck",
        help="Run type checking.",
    )

    subparsers.add_parser(
        "security",
        help="Run dependency security checks.",
    )

    subparsers.add_parser(
        "all",
        help="Run the complete CI/evaluation pipeline.",
    )

    return parser


def main() -> int:
    args = parser().parse_args()

    commands = {
        "check": check_environment,
        "install": install,
        "migrate": migrate,
        "test": test,
        "eval": evaluate,
        "seed": seed,
        "lint": lint,
        "format": format_check,
        "typecheck": type_check,
        "security": security_check,
        "all": all_checks,
    }

    commands[args.command]()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
