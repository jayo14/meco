from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config.settings import get_settings

settings = get_settings()

is_sqlite = settings.database_url.startswith("sqlite")
engine_kwargs = {
    "echo": False,
    "pool_pre_ping": settings.db_pool_pre_ping,
}

if not is_sqlite:
    engine_kwargs.update(
        {
            "pool_recycle": settings.db_pool_recycle,
            "pool_size": settings.db_pool_size,
            "max_overflow": settings.db_max_overflow,
            "pool_timeout": settings.db_pool_timeout,
        }
    )

engine = create_async_engine(
    settings.database_url,
    **engine_kwargs,
)

SessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
async_session_factory = SessionLocal


async def get_db():
    """Dependency yielding async session with automatic resource cleanup."""
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
