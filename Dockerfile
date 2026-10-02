FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN python -m pip install --no-cache-dir --disable-pip-version-check .

EXPOSE 10000

CMD ["uvicorn", "agent_platform.api.main:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "10000", "--workers", "1"]
