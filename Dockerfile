FROM python:3.11-slim AS base

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    netcat-openbsd \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

COPY . .

ENV GCP_SIM_HOST=0.0.0.0
ENV GCP_SIM_PORT=9099

EXPOSE 9099

CMD ["gcp-sim", "start", "--all", "--no-docker"]
