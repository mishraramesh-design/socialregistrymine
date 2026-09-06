import os

from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("CONNECTOR_DB_URL", "sqlite:///./data/connectors.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)

if DATABASE_URL.startswith("sqlite"):
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


def _sqlite_literal(value):
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    if isinstance(value, bool):
        return "1" if value else "0"
    return str(value)


def add_missing_columns():
    """There's no Alembic here — just create_all(), which only creates tables
    that don't exist yet and never alters ones that do. A long-lived SQLite
    file from before a model change (e.g. a Docker volume that survives many
    redeploys) would otherwise 500 the instant code touches a column the
    file doesn't have. Adds whatever the models declare but an existing
    table is missing, backfilling NOT NULL columns with their model default
    so existing rows stay valid. SQLite-only; a real RDBMS in production
    would use a proper migration tool instead."""
    if engine.dialect.name != "sqlite":
        return
    with engine.connect() as conn:
        for table in Base.metadata.sorted_tables:
            existing_columns = {
                row[1] for row in conn.exec_driver_sql(f'PRAGMA table_info("{table.name}")')
            }
            if not existing_columns:
                continue  # table doesn't exist yet — create_all() will make it
            for column in table.columns:
                if column.name in existing_columns:
                    continue
                col_type = column.type.compile(dialect=engine.dialect)
                clause = f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {col_type}'
                if not column.nullable:
                    default = column.default.arg if column.default is not None else 0
                    clause += f" NOT NULL DEFAULT {_sqlite_literal(default)}"
                conn.exec_driver_sql(clause)
        conn.commit()
