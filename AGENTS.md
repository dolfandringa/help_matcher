# Help Matcher agent guide

## Project purpose

Help Matcher is a disaster-relief matching tool for quickly recording people who need help and people who can offer help. The backend is FastAPI with SQLModel/Pydantic models and PostgreSQL/PostGIS storage. The UI is designed to be easy for non-technical users, with WhatsApp chatbot intake and a map/search interface for finding matching offers and demands.

## Important architecture

- `src/help_matcher/main.py` wires the FastAPI application, API routers, webhook routes, health checks, and frontend static serving.
- `src/help_matcher/models/` contains SQLModel database models and API schemas. Offers and demands share help-record concepts: original message, tags, contact links, status, location fields, geometry, and optional public IDs.
- `src/help_matcher/management.py` defines Poetry console commands:
  - `poetry run serve --reload`
  - `poetry run create_admin --username USER --password PASS`
  - `poetry run load_sample_data --clear-existing`
- `src/help_matcher/whatsapp/` contains WhatsApp conversation state, action helpers, reply sending, and chatbot orchestration. The LLM functions are placeholders; keep orchestration separate from future LLM implementation.
- `src/help_matcher/local_whatsapp.py` provides the development-only local WhatsApp simulator.
- `src/help_matcher/geocoding/` contains provider dispatch plus Nominatim and Geoapify implementations. The shared wrapper builds query variants, asks the configured provider once, and chooses the candidate with the highest confidence. Nominatim uses fixed confidence `0.5`; Geoapify uses API confidence.
- `src/frontend/` contains the Vite/React frontend. FastAPI serves the built frontend from `dist/` in the combined app.
- `alembic/` contains database migrations. Model changes that affect persisted schema must include an Alembic migration.

## Design choices to preserve

- Keep data entry easy. WhatsApp users should be able to send natural text; the backend stores the original help message and extracted fields.
- Offers and demands can be closed rather than deleted when help is no longer available or needed.
- Regular users are identified primarily through WhatsApp contact details/BSUID. Admin users authenticate separately.
- Location supports both administrative areas and specific addresses. Geometry may be a point or polygon so records can later be matched and visualized on a map.
- Public IDs are user-friendly and may be user-scoped for chatbot-created records; do not assume they are globally unique unless the schema is changed.
- Geocoding should be resilient. If a provider fails while loading sample data, the loader uses fallback points, but provider code should still surface real errors rather than silently swallowing them.
- Configuration is environment-driven through `pydantic-settings`. When adding config settings, update `src/help_matcher/config.py`, `.env.example`, and `docker-compose.yml`.

## Running locally

The fastest full-stack path is:

```bash
cp .env.example .env
docker compose up --build
```

Backend-only development:

```bash
poetry install
cp .env.example .env
poetry run serve --reload
```

Frontend-only development:

```bash
npm install
npm run frontend:dev
```

Load demo data:

```bash
poetry run load_sample_data --clear-existing
```

## Testing and verification

Use the smallest command that covers the change.

Common backend checks:

```bash
poetry run python -m compileall -q src tests alembic
poetry run pytest tests/unittests/test_geocoding.py -q
poetry run pytest tests/unittests/test_whatsapp.py -q
poetry run pytest tests/e2e/test_chatbot_conversation.py -q
```

For management/sample-data changes, also run or dry-run the relevant command against a local PostGIS database:

```bash
poetry run load_sample_data --clear-existing
```

For frontend changes:

```bash
npm run frontend:build
```

If dependencies are missing, install with the existing package manager only (`poetry install` or `npm install`). Do not add new tooling just for validation.

## Local WhatsApp simulator

In development, open:

```text
http://localhost:8000/local-whatsapp
```

The simulator sends unsigned Meta-shaped webhook payloads to the backend and receives bot replies through the fake local Graph endpoint. Conversations are isolated by WhatsApp BSUID.

Use the real Meta Graph API base URL only outside local simulation:

```env
META_API_BASE_URL=https://graph.facebook.com
```

## Geocoding notes

- `GEOCODER_PROVIDER` selects `nominatim` or `geoapify`.
- `GEOCODING_LOCATION_SUFFIXES` controls query variants. Keep suffixes targeted to the expected region when possible.
- Geoapify batch geocoding sends all query variants in a single batch job and polls for completion.
- Geoapify batch jobs can take longer than an individual HTTP request; keep `GEOAPIFY_BATCH_TIMEOUT_SECONDS` high enough for sample-data loading.
- When changing geocoding behavior, verify all sample records and include confidence/coordinate checks where practical.

## Code-change expectations

- Keep changes surgical and preserve current behavior unless the task explicitly asks for a behavior change.
- Add or update tests for schema, API, chatbot, geocoding, and migration behavior when those areas change.
- Do not commit secrets or real phone numbers/API keys.
- Prefer existing helpers and patterns over adding parallel implementations.

## Migration instructions for agents

- Use Alembic for every persisted schema change.
- After changing SQLModel models, generate a revision from the project root:

```bash
poetry run alembic revision --autogenerate -m "describe the change"
```

- Always inspect and edit the generated file in `alembic/versions/`; autogenerated migrations are a starting point, not something to trust blindly.
- Confirm new tables, columns, indexes, constraints, enums, relationship tables, and PostGIS/GeoAlchemy columns are represented correctly.
- Confirm nullable/default choices are safe for existing rows.
- Include explicit data migrations when existing data must be backfilled, transformed, normalized, linked, or otherwise made compatible with a schema change.
- Do not rely on application startup, sample-data loading, or manual SQL to make production data compatible with a schema change.
- Run migrations with:

```bash
poetry run alembic upgrade head
```

## Configuration instructions for agents

When adding or renaming runtime configuration, keep all config surfaces in sync:

- `src/help_matcher/config.py`
- `.env.example`
- `docker-compose.yml`

Do this in the same change as the code that consumes the setting.
