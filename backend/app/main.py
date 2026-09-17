"""
app/main.py - FastAPI application entry point.
"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.models  # noqa: F401 - ensure all models are registered with SQLAlchemy

from app.routers import cameras, events, vehicles, alerts, watchlist
from app.auth import router as auth_router

app = FastAPI(
    title="CCTV GIS PoC",
    description=(
        "Centralised CCTV Registry & GIS Mapping — PoC API.\n\n"
        "**Auth flow**: POST /api/auth/login → get JWT → send as `Authorization: Bearer <token>`\n\n"
        "Key flow: **POST /api/events** → watchlist match → auto-alert → vehicle history → GIS route."
    ),
    version="1.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS", "http://localhost:5173,http://localhost:3000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
#
# Table creation/schema changes are handled entirely by Alembic
# (`alembic upgrade head`) — the async engine intentionally has no
# equivalent of the old synchronous create_all()-on-startup.
# ---------------------------------------------------------------------------

app.include_router(auth_router.router)   # /api/auth/login, /api/auth/me
app.include_router(cameras.router)
app.include_router(events.router)
app.include_router(vehicles.router)
app.include_router(alerts.router)
app.include_router(watchlist.router)
from app.routers import dashboard, simulator, camera_feed
app.include_router(dashboard.router)
app.include_router(simulator.router)
app.include_router(camera_feed.router)


# ---------------------------------------------------------------------------
# Health check (public)
# ---------------------------------------------------------------------------

@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}
