"""
app/main.py - FastAPI application entry point.
"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, Base

# Import all models so SQLAlchemy creates all tables
import app.models  # noqa: F401

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
# DB tables on startup
# ---------------------------------------------------------------------------

@app.on_event("startup")
def create_tables():
    Base.metadata.create_all(bind=engine)


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(auth_router.router)   # /api/auth/login, /api/auth/me
app.include_router(cameras.router)
app.include_router(events.router)
app.include_router(vehicles.router)
app.include_router(alerts.router)
app.include_router(watchlist.router)
from app.routers import dashboard, simulator
app.include_router(dashboard.router)
app.include_router(simulator.router)


# ---------------------------------------------------------------------------
# Health check (public)
# ---------------------------------------------------------------------------

@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}
