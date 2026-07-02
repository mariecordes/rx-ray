FROM python:3.11.15-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY . .

RUN python -m pip install --upgrade pip \
    && python -m pip install ".[llm]"

EXPOSE 8080

CMD ["sh", "scripts/railway_start.sh"]
