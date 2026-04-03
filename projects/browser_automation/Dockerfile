FROM mcr.microsoft.com/playwright/python:v1.58.0-jammy

WORKDIR /app

RUN pip install --no-cache-dir poetry \
    && poetry config virtualenvs.create false

COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root --no-interaction

COPY projects/cli ./cli
COPY projects/lib ./lib
COPY projects/models ./models
COPY projects/browser_automation ./browser_automation

CMD ["python", "-m", "browser_automation.hello_world"]
