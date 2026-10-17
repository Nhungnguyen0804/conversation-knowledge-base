from app.models import Base


def test_metadata_registers_all_tables():
    assert {"conversations", "chat_messages"} <= set(Base.metadata.tables)
