"""
Test SQLite Database Isolation Helper

Prevents standalone verification and regression suites from writing synthetic
documents, chunks, conversations, or query caches into the normal development
database (`documents.db`). Each run executes against a temporary WAL-safe
SQLite clone that is disposed and removed on exit.
"""

import contextlib
import gc
import sqlite3
import tempfile
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core import database as db_module
from app.core.database import Base, DB_PATH, get_db
from app.main import app


@contextlib.contextmanager
def isolated_test_db(clone_dev_db: bool = True):
    """
    Create an isolated temporary SQLite database and bind both FastAPI
    dependency overrides (`get_db`) and module-level `SessionLocal` / `engine`
    for the duration of the context block.
    """
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        tmp_db_path = Path(tmp_dir) / "test_isolated.db"

        if clone_dev_db and DB_PATH.exists():
            src_conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
            dst_conn = sqlite3.connect(tmp_db_path.as_posix())
            try:
                src_conn.backup(dst_conn)
            finally:
                dst_conn.close()
                src_conn.close()

        temp_engine = create_engine(
            f"sqlite:///{tmp_db_path.as_posix()}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(bind=temp_engine)
        TestingSessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=temp_engine,
        )

        def override_get_db():
            session = TestingSessionLocal()
            try:
                yield session
            finally:
                session.close()

        prev_override = app.dependency_overrides.get(get_db)
        prev_engine = db_module.engine
        prev_session_local = db_module.SessionLocal

        app.dependency_overrides[get_db] = override_get_db
        db_module.engine = temp_engine
        db_module.SessionLocal = TestingSessionLocal

        session = TestingSessionLocal()
        try:
            yield session, TestingSessionLocal, tmp_db_path
        finally:
            session.close()
            if prev_override is not None:
                app.dependency_overrides[get_db] = prev_override
            else:
                app.dependency_overrides.pop(get_db, None)
            db_module.engine = prev_engine
            db_module.SessionLocal = prev_session_local
            temp_engine.dispose()
            gc.collect()

