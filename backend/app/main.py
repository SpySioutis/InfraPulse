"""InfraPulse backend: FastAPI application entrypoint."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import auth, database
from app.routers import (
    agents,
    alerts,
    auth as auth_router,
    dashboard,
    groups,
    health,
    ingest,
    metrics,
    servers,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("infrapulse")


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    logger.info("InfraPulse backend starting")
    with database.SessionLocal() as db:
        try:
            auth.ensure_admin(db)
        except RuntimeError as exc:
            logger.error("%s", exc)
            raise
    yield
    logger.info("InfraPulse backend stopping")


app = FastAPI(
    title="InfraPulse API",
    version="0.1.0",
    description="Self-hosted infrastructure monitoring API: servers, agents, metrics, alerts.",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(auth_router.router, prefix="/api")
app.include_router(groups.router, prefix="/api")
app.include_router(servers.router, prefix="/api")
app.include_router(agents.router, prefix="/api")
app.include_router(ingest.router, prefix="/api")
app.include_router(metrics.router, prefix="/api")
app.include_router(alerts.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
