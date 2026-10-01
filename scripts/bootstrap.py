"""Project checks and repeatable developer commands; this script starts no services."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*command: str) -> None:
    subprocess.run(command, cwd=ROOT, check=True)


def check() -> None:
    if sys.version_info < (3, 13):  # noqa: UP036 - also guard direct script execution
        raise SystemExit("Python 3.13 or newer is required.")
    missing = [
        key
        for key in ("DATABASE_URL", "OIDC_ISSUER_URL", "OIDC_AUDIENCE")
        if not os.environ.get(key)
    ]
    if missing:
        print(f"Environment variables not set (required for deployment): {', '.join(missing)}")
    else:
        print("Required database and OIDC settings are present.")
    print(f"Python {sys.version.split()[0]} is supported.")


def format_code() -> None:
    run(sys.executable, "-m", "ruff", "format", ".")


def lint() -> None:
    run(sys.executable, "-m", "ruff", "check", ".")


def typecheck() -> None:
    run(sys.executable, "-m", "mypy", "src", "tests")


def ci() -> None:
    check()
    run(sys.executable, "-m", "ruff", "format", "--check", ".")
    lint()
    typecheck()
    run(sys.executable, "-m", "pytest")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=(
            "check",
            "format",
            "lint",
            "typecheck",
            "test",
            "eval",
            "migrate",
            "seed",
            "ci",
        ),
        nargs="?",
        default="check",
    )
    args = parser.parse_args()

    commands = {
        "check": check,
        "format": format_code,
        "lint": lint,
        "typecheck": typecheck,
        "test": lambda: run(sys.executable, "-m", "pytest"),
        "eval": lambda: run(sys.executable, "-m", "agent_platform.evaluations.runner"),
        "migrate": lambda: run(sys.executable, "-m", "alembic", "upgrade", "head"),
        "seed": lambda: run(sys.executable, "-m", "agent_platform.seed"),
        "ci": ci,
    }
    commands[args.command]()


if __name__ == "__main__":
    main()
