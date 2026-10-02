"""App metadata database (users, companies, connections, formats, runs) via SQLModel."""

from collections.abc import Iterator

from sqlmodel import Session, SQLModel, create_engine

from app.config import get_settings

engine = create_engine(get_settings().database_url, connect_args={"check_same_thread": False})


def init_db() -> None:
    # Import table models so they register on SQLModel.metadata before create_all.
    import app.models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
