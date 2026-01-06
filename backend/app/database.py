"""
SheetFlow AI - Database Configuration
Async SQLAlchemy engine and session management for PostgreSQL.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from typing import AsyncGenerator

from app.config import get_settings

# Create async engine
settings = get_settings()
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# Session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Base class for models
Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that provides a database session.
    
    Usage in FastAPI:
        @router.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """
    Create all tables. Call during application startup.
    
    NOTE: In development, this drops and recreates all tables to ensure
    the schema matches the models. In production, use proper migrations (Alembic).
    """
    async with engine.begin() as conn:
        # Drop all tables with CASCADE to handle foreign key dependencies
        # This also handles orphaned tables not in current metadata
        # WARNING: This deletes all data! Use migrations in production.
        from sqlalchemy import text
        
        # Get all tables in the database and drop them with CASCADE
        result = await conn.execute(text("""
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'public'
        """))
        tables = result.fetchall()
        
        for (table_name,) in tables:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{table_name}" CASCADE'))
        
        # Now create all tables from current models
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Close database connections. Call during application shutdown."""
    await engine.dispose()
