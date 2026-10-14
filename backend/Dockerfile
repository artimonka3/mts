FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app/backend

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock ./requirements.lock
RUN python -m pip install --no-cache-dir --require-hashes -r requirements.lock

COPY pyproject.toml ./pyproject.toml
COPY src ./src
RUN python -m pip install --no-cache-dir --no-deps . \
    && groupadd --gid 10001 mts \
    && useradd --uid 10001 --gid mts --no-create-home --shell /usr/sbin/nologin mts

COPY alembic.ini ./alembic.ini
COPY alembic ./alembic

USER 10001:10001
EXPOSE 8000

CMD ["python", "-m", "uvicorn", "mts_backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
