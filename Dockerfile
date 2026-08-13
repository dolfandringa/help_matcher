FROM node:22-slim AS frontend

WORKDIR /app

COPY package.json package-lock.json* tsconfig.json tsconfig.node.json vite.config.ts index.html ./
COPY src/frontend ./src/frontend
RUN npm install && npm run frontend:build


FROM python:3.12-slim AS backend

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VERSION=1.8.5 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false

WORKDIR /app

RUN pip install --no-cache-dir "poetry==$POETRY_VERSION"

COPY pyproject.toml poetry.lock* README.md ./
RUN poetry install --only main --no-root

COPY src ./src
COPY alembic.ini ./
COPY alembic ./alembic
COPY docker-entrypoint.sh ./

RUN poetry install --only main
RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["serve"]


FROM backend AS combined

COPY --from=frontend /app/dist ./dist
