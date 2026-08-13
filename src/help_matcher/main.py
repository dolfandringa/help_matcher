from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from help_matcher.api import router as api_router
from help_matcher.auth import router as auth_router
from help_matcher.webhooks import router as webhook_router


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield


app = FastAPI(
    title="Help Matcher API",
    summary="Backend for disaster help demands, offers, and WhatsApp bot intake.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(api_router)
app.include_router(auth_router)
app.include_router(webhook_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
