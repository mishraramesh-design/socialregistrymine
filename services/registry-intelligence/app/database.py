import os

from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("REGISTRY_DB_URL", "sqlite:///./data/registry.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)

if DATABASE_URL.startswith("sqlite"):
    # See services/consent-management/app/database.py for why: some sandboxed/
    # overlay filesystems reject the POSIX locks SQLite's default rollback
    # journal needs, surfacing as "attempt to write a readonly database" on the
    # second concurrent connection. In-memory journaling avoids that file.
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=MEMORY")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
