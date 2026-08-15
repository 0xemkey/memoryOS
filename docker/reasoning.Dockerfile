FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN useradd --create-home --uid 10002 memoryos
WORKDIR /app

COPY pyproject.toml README.md /app/
COPY apps /app/apps
COPY packages /app/packages
COPY migrations /app/migrations

RUN pip install --no-cache-dir .

USER memoryos
EXPOSE 8772

CMD ["uvicorn", "apps.reasoning_service.main:app", "--host", "0.0.0.0", "--port", "8772"]
