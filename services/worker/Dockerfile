FROM python:3.13.1-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.lock /app/requirements.lock
RUN python -m pip install --no-cache-dir -r /app/requirements.lock
COPY services/api /app/services/api
COPY services/worker /app/services/worker
COPY packages/contracts/openapi.json /app/packages/contracts/openapi.json
ENV PYTHONPATH=/app/services/api/src:/app/services/worker/src

WORKDIR /app/services/worker
CMD ["celery", "-A", "mirror_worker.app:celery_app", "worker", "--loglevel=INFO"]
