import os
from collections.abc import Iterator
from pathlib import Path
from typing import Annotated

from fastapi import Depends
from sqlalchemy import Engine, event
from sqlmodel import Session, SQLModel, create_engine

# Image/local default: SQLite in ./data (git-ignored; /app/data in the container).
# Compose sets postgresql+psycopg://...@db:5432/eliezer.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/app.db")


def make_engine(url: str, **kwargs) -> Engine:
    if not url.startswith("sqlite"):
        # pre_ping replaces connections Postgres closed (e.g. after a db restart).
        return create_engine(url, pool_pre_ping=True, **kwargs)
    engine = create_engine(url, connect_args={"check_same_thread": False}, **kwargs)

    @event.listens_for(engine, "connect")
    def enforce_foreign_keys(dbapi_connection, _connection_record) -> None:
        # SQLite ignores foreign keys unless asked; Postgres always enforces them.
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    return engine


engine = make_engine(DATABASE_URL)


def create_db_and_tables() -> None:
    db_file = (
        engine.url.database if engine.url.drivername.startswith("sqlite") else None
    )
    if db_file:  # None for in-memory SQLite and for Postgres
        Path(db_file).parent.mkdir(parents=True, exist_ok=True)
    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
