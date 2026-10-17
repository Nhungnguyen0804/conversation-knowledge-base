import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db import create_db_engine


@pytest.fixture
def engine(tmp_path):
    eng = create_db_engine(f"sqlite:///{tmp_path / 'test.db'}")
    yield eng
    eng.dispose()


def test_pragmas_applied(engine) -> None:
    with engine.connect() as conn:
        assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1
        assert conn.execute(text("PRAGMA journal_mode")).scalar() == "wal"
        assert conn.execute(text("PRAGMA busy_timeout")).scalar() == 5000


def test_foreign_key_is_enforced(engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE parent (id INTEGER PRIMARY KEY)"))
        conn.execute(
            text(
                "CREATE TABLE child (id INTEGER PRIMARY KEY, "
                "parent_id INTEGER REFERENCES parent(id))"
            )
        )

    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO child (parent_id) VALUES (999)"))