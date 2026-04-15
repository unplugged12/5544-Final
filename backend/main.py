"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database import init_db
from routes import announcements, chat as chat_routes, faq, health, history, moderation
from routes import metrics as metrics_routes
from routes import settings as settings_routes
from routes import sources
from services import retrieval_service

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown hooks."""
    logger.info("Starting up — initializing database and retrieval service")
    await init_db()
    retrieval_service.init()
    logger.info("Startup complete")
    yield
    logger.info("Shutting down")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Esports Community Mod Copilot API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — must be added BEFORE routes
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(health.router, prefix="/api")
app.include_router(sources.router, prefix="/api")
app.include_router(faq.router, prefix="/api/faq")
app.include_router(announcements.router, prefix="/api/announcements")
app.include_router(moderation.router, prefix="/api/moderation")
app.include_router(settings_routes.router, prefix="/api/settings")
app.include_router(history.router, prefix="/api/history")
app.include_router(chat_routes.router, prefix="/api")
app.include_router(metrics_routes.router)  # prefix already set to /api/metrics in the module
