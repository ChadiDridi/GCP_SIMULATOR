from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from gcp_simulator.app.config import settings

_is_sqlite = settings.database_url.startswith("sqlite")
_engine_kwargs: dict = {"echo": False}
if not _is_sqlite:
    _engine_kwargs.update({"pool_size": 10, "max_overflow": 20})
else:
    # SQLite needs connect_args for same-thread safety in async contexts
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_async_engine(settings.database_url, **_engine_kwargs)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
