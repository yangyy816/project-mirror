FROM python:3.13.1-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.lock /app/requirements.lock
RUN python -m pip install --no-cache-dir -r /app/requirements.lock
COPY services/api /app/services/api
COPY packages/contracts/openapi.json /app/packages/contracts/openapi.json
ENV PYTHONPATH=/app/services/api/src

WORKDIR /app/services/api
EXPOSE 8000
CMD ["uvicorn", "mirror_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
