from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine

DATABASE_URL = "sqlite:///./knowledge.db"


def create_db_engine(url: str = DATABASE_URL) -> Engine:
    engine = create_engine(
        url,
        # FastAPI chạy endpoint sync trong threadpool,
        # nên một connection có thể được dùng bởi thread khác nơi nó được tạo
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")  # đợi tối đa 5000 ms khi DB bị khóa
        cursor.close()

    return engine


engine = create_db_engine()