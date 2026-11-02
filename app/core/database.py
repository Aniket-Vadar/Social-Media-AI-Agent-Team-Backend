from typing import AsyncGenerator
import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.core.config import settings
from app.models.models import Base

logger = logging.getLogger(__name__)

# Determine if we have a valid PostgreSQL URL or need SQLite fallback for local offline testing
db_url = settings.DATABASE_URL
engine_kwargs = {"echo": False, "future": True}

if "sqlite" in db_url:
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # Production PostgreSQL / Supabase connection pooling configuration
    engine_kwargs.update({
        "pool_size": 20,
        "max_overflow": 10,
        "pool_pre_ping": True,
        "pool_recycle": 3600,
    })
    # Supabase Connection Pooler (PgBouncer IPv4) compatibility for asyncpg
    if "pooler.supabase.co" in db_url or ":6543" in db_url:
        engine_kwargs["connect_args"] = {
            "statement_cache_size": 0,
            "prepared_statement_cache_size": 0
        }


try:
    engine = create_async_engine(db_url, **engine_kwargs)
except Exception as e:
    logger.warning(f"Could not connect to {db_url}, falling back to local SQLite: {e}")
    db_url = "sqlite+aiosqlite:///./socialix.db"
    engine = create_async_engine(db_url, connect_args={"check_same_thread": False})

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that provides an async database session per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Create all tables if they do not exist and ensure seed data."""
    from sqlalchemy import select
    from app.models.models import Workspace, User, Campaign

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed default workspace and campaign if not existing
    async with AsyncSessionLocal() as session:
        try:
            ws_check = await session.execute(
                select(Workspace).where(Workspace.id == "ws-default-tubeguruji")
            )
            if not ws_check.scalar_one_or_none():
                ws = Workspace(
                    id="ws-default-tubeguruji",
                    name="Tubeguruji Socialix Workspace",
                    owner_id="user-saloni"
                )
                session.add(ws)
                await session.flush()

                camp_check = await session.execute(
                    select(Campaign).where(Campaign.id == "camp-tubeguruji-instagram")
                )
                if not camp_check.scalar_one_or_none():
                    camp = Campaign(
                        id="camp-tubeguruji-instagram",
                        workspace_id="ws-default-tubeguruji",
                        name="Tubeguruji Instagram",
                        goal="Grow brand awareness with autonomous multi-agent social content",
                        brand_voice={"tone": "professional, engaging", "banned_words": []},
                        status="active"
                    )
                    session.add(camp)
                await session.commit()
        except Exception as e:
            logger.warning(f"Seed workspace check: {e}")
            await session.rollback()

    logger.info("Database initialized successfully.")

