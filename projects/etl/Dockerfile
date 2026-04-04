FROM mcr.microsoft.com/playwright/python:v1.58.0-jammy

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl unzip xvfb \
    && rm -rf /var/lib/apt/lists/*

ARG CAPSOLVER_EXT_VERSION=v.1.17.0
ARG CAPSOLVER_EXT_ZIP=CapSolver.Browser.Extension-chrome-v1.17.0.zip
RUN curl -fsSL \
    "https://github.com/capsolver/capsolver-browser-extension/releases/download/${CAPSOLVER_EXT_VERSION}/${CAPSOLVER_EXT_ZIP}" \
    -o /tmp/capsolver.zip \
    && unzip -q /tmp/capsolver.zip -d /opt/capsolver-extension \
    && rm /tmp/capsolver.zip

RUN pip install --no-cache-dir poetry \
    && poetry config virtualenvs.create false

COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root --no-interaction

COPY projects/cli ./cli
COPY projects/lib ./lib
COPY projects/models ./models
COPY projects/etl ./etl
RUN chmod +x /app/etl/docker-entrypoint.sh

ENV PYTHONUNBUFFERED=1
ENV CAPSOLVER_EXTENSION_PATH=/opt/capsolver-extension

ENTRYPOINT ["/app/etl/docker-entrypoint.sh"]
