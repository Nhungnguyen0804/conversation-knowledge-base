import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from app.models import ChatMessage, Conversation


def make_conv(**kw) -> Conversation:
    return Conversation(title=kw.get("title", "demo"), full_text=kw.get("full_text", "x"))


def make_msg(index: int, **kw) -> ChatMessage:
    return ChatMessage(
        message_index=index,
        role=kw.get("role", "me"),
        content=kw.get("content", "hi"),
        start_offset=kw.get("start", 0),
        end_offset=kw.get("end", 2),
    )


def count_messages(session) -> int:
    return session.scalar(select(func.count()).select_from(ChatMessage))


def test_conversation_gets_uuid_and_timestamps(session):
    conv = make_conv()
    session.add(conv)
    session.commit()

    assert len(conv.id) == 36
    assert conv.created_at is not None
    assert conv.updated_at is not None


def test_ids_are_unique(session):
    a, b = make_conv(), make_conv()
    session.add_all([a, b])
    session.commit()

    assert a.id != b.id


def test_relationship_both_directions(session):
    conv = make_conv()
    msg = make_msg(0)
    conv.chat_messages.append(msg)
    session.add(conv)
    session.commit()

    assert msg.conversation is conv
    assert msg.conversation_id == conv.id
    assert conv.chat_messages == [msg]


def test_messages_ordered_by_message_index(session):
    conv = make_conv()
    conv.chat_messages.extend([make_msg(2), make_msg(0), make_msg(1)])
    session.add(conv)
    session.commit()
    session.expire_all()

    assert [m.message_index for m in conv.chat_messages] == [0, 1, 2]


def test_updated_at_changes_on_update(session):
    import time

    conv = make_conv()
    session.add(conv)
    session.commit()
    before = conv.updated_at

    time.sleep(0.01)
    conv.title = "đổi tên"
    session.commit()

    assert conv.updated_at > before


def test_delete_conversation_cascades_to_messages(session):
    conv = make_conv()
    conv.chat_messages.extend([make_msg(0), make_msg(1)])
    session.add(conv)
    session.commit()

    session.delete(conv)
    session.commit()

    assert count_messages(session) == 0


def test_db_level_cascade_without_orm(session):
    """Xóa bằng SQL thô: chứng minh ondelete=CASCADE + PRAGMA hoạt động."""
    conv = make_conv()
    conv.chat_messages.append(make_msg(0))
    session.add(conv)
    session.commit()

    session.execute(text("DELETE FROM conversations"))
    session.commit()

    assert count_messages(session) == 0


def test_foreign_key_is_enforced(session):
    orphan = make_msg(0)
    orphan.conversation_id = "khong-ton-tai"
    session.add(orphan)

    with pytest.raises(IntegrityError):
        session.commit()


def test_duplicate_message_index_rejected(session):
    conv = make_conv()
    conv.chat_messages.extend([make_msg(0), make_msg(0)])
    session.add(conv)

    with pytest.raises(IntegrityError):
        session.commit()