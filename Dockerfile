FROM mcr.microsoft.com/playwright/python:v1.58.0-jammy

WORKDIR /app

RUN pip install --no-cache-dir poetry \
    && poetry config virtualenvs.create false

COPY pyproject.toml ./
RUN poetry install --no-root --no-interaction

COPY . .

CMD ["python", "-m", "browser_glue.hello_world"]
