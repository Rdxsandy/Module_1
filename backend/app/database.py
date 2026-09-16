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

# asyncpg doesn't understand libpq-only query params (sslmode, channel_binding);
# translate sslmode into an asyncpg connect arg and drop the rest.
_url = make_url(DATABASE_URL).set(drivername="postgresql+asyncpg")
_query = dict(_url.query)
_sslmode = _query.pop("sslmode", None)
_query.pop("channel_binding", None)
_url = _url.set(query=_query)

connect_args = {"ssl": True} if _sslmode and _sslmode.lower() != "disable" else {}
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
engine = create_async_engine(
    _url,
    connect_args=connect_args,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=1800,
    echo=False,
)

# expire_on_commit=False: FastAPI route handlers return ORM objects straight to
# Pydantic (response_model). Without this, attribute access after a commit would
# trigger an implicit lazy load, which raises under async SQLAlchemy.
SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)

Base = declarative_base()


async def get_db():
    """FastAPI dependency that yields an async DB session and closes it afterwards."""
    async with SessionLocal() as db:
        yield db
