"""
database.py — Async SQLAlchemy engine + session factory (asyncpg).

Uses Neon (PostgreSQL) via DATABASE_URL in .env, with the app talking to
it over asyncpg so DB I/O never blocks FastAPI's event loop. Alembic
migrations still run over a plain sync (psycopg2) connection derived from
the same env var — see alembic/env.py.
"""
import os
from dotenv import load_dotenv
load_dotenv()

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set. Configure your Neon PostgreSQL connection string in .env.")


def build_engine_and_sessionmaker(*, pool_size: int = 20, max_overflow: int = 10):
    """Build a fresh async engine + sessionmaker against DATABASE_URL.

    asyncpg connections are bound to the event loop that opened them and
    must never be shared across loops — every event loop that touches the
    DB (the main FastAPI loop, or a background worker loop like the camera
    feed's) needs its OWN engine/pool from this, not the same `engine`
    object reused across loops.
    """
    # asyncpg doesn't understand libpq-only query params (sslmode, channel_binding);
    # translate sslmode into an asyncpg connect arg and drop the rest.
    url = make_url(DATABASE_URL).set(drivername="postgresql+asyncpg")
    query = dict(url.query)
    sslmode = query.pop("sslmode", None)
    query.pop("channel_binding", None)
    url = url.set(query=query)

    connect_args = {"ssl": True} if sslmode and sslmode.lower() != "disable" else {}
    # IMPORTANT: DATABASE_URL must point at Neon's *direct* endpoint, not the
    # "-pooler" (PgBouncer transaction-pooling) one. This app keeps its own
    # long-lived connection pool (pool_size/max_overflow below), so pooling
    # again via PgBouncer double-pools — and PgBouncer's transaction mode can
    # silently hand a "connection" different physical Postgres backends between
    # statements, which breaks asyncpg's server-side prepared statements
    # (surfaces as asyncpg.exceptions.InvalidCachedStatementError). Serverless/
    # edge callers without a persistent pool should use "-pooler" instead.
    # statement_cache_size=0 is kept as defense-in-depth even on the direct
    # endpoint, in case this ever runs through a pooler again.
    connect_args["statement_cache_size"] = 0

    # Pool sized for concurrent request bursts (e.g. camera fleets pushing events);
    # pre_ping + recycle guard against Neon's pooler silently dropping idle connections.
    built_engine = create_async_engine(
        url,
        connect_args=connect_args,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=True,
        pool_recycle=1800,
        echo=False,
    )

    # expire_on_commit=False: FastAPI route handlers return ORM objects straight to
    # Pydantic (response_model). Without this, attribute access after a commit would
    # trigger an implicit lazy load, which raises under async SQLAlchemy.
    built_sessionmaker = async_sessionmaker(
        bind=built_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )
    return built_engine, built_sessionmaker


engine, SessionLocal = build_engine_and_sessionmaker()

Base = declarative_base()


async def get_db():
    """FastAPI dependency that yields an async DB session and closes it afterwards."""
    async with SessionLocal() as db:
        yield db
