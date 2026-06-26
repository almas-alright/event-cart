"""Database engine, session, and metadata helpers."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from eventcart.config import get_settings


class Base(DeclarativeBase):
    pass


def create_database_engine(database_url: str | None = None):
    return create_engine(database_url or get_settings().database_url)


engine = create_database_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session

