from contextlib import asynccontextmanager

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import redis.asyncio as aioredis
from slowapi.errors import RateLimitExceeded
from slowapi.extension import _rate_limit_exceeded_handler
from slowapi.middleware import SlowAPIMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.core.rate_limiter import limiter
from app.services.email.mail_service import mail_service
from app.worker.scheduler import bind_arq_pool, clear_arq_pool, scheduler

configure_logging()

openapi_url = None if settings.ENVIRONMENT == "production" else "/openapi.json"


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.arq_pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    app.state.redis = await aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    bind_arq_pool(app.state.arq_pool)
    if not scheduler.running:
        scheduler.start()
    try:
        if settings.email_enabled:
            await mail_service.verify_connection()
        yield
    finally:
        if scheduler.running:
            scheduler.shutdown()
        clear_arq_pool()
        await app.state.redis.aclose()
        await app.state.arq_pool.close()


app = FastAPI(title="Project Atlas", version="1.0.0", openapi_url=openapi_url, lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
