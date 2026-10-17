import pytest
from sqlalchemy import func, select

from app.conversation_service import (
    DEFAULT_TITLE,
    NoMessagesError,
    make_title,
    preview,
    save,
)
from app.models import ChatMessage, Conversation
from app.parser import parse

SAMPLE = (
    "@me: Làm sao chạy pre-commit cho một file?\n"
    "@chat: Dùng lệnh:\n"
    "```bash\n"
    "uv run pre-commit run --files tests/test_health.py\n"
    "@me: dòng này nằm trong code\n"
    "```\n"
    "@me: Còn chạy cho cả repo?\n"
    "@chat: Thêm --all-files.\n"
)


def count(session, model) -> int:
    return session.scalar(select(func.count()).select_from(model))


# ---------- preview ----------

def test_preview_counts_and_title():
    p = preview(SAMPLE)

    assert p.message_count == 4
    assert (p.me_count, p.chat_count) == (2, 2)
    assert p.suggested_title == "Làm sao chạy pre-commit cho một file?"
    assert p.warnings == []


def test_preview_does_not_touch_db(session):
    preview(SAMPLE)

    assert count(session, Conversation) == 0
    assert count(session, ChatMessage) == 0


def test_preview_passes_warnings_through():
    p = preview("@me: a\n```bash\nls")

    assert [w.code for w in p.warnings] == ["unclosed_fence"]


def test_preview_without_messages():
    p = preview("chỉ là chữ thường")

    assert p.message_count == 0
    assert p.suggested_title == DEFAULT_TITLE
    assert [w.code for w in p.warnings] == ["no_marker"]


# ---------- save ----------

def test_save_writes_conversation_and_messages(session):
    conv = save(session, SAMPLE)

    assert count(session, Conversation) == 1
    assert count(session, ChatMessage) == 4
    assert len(conv.id) == 36
    assert [m.message_index for m in conv.chat_messages] == [0, 1, 2, 3]
    assert [m.role for m in conv.chat_messages] == ["me", "chat", "me", "chat"]
    assert conv.title == "Làm sao chạy pre-commit cho một file?"
    assert conv.full_text == SAMPLE


def test_saved_offsets_hold_after_reload(session):
    conv = save(session, SAMPLE)
    conv_id = conv.id
    session.expire_all()

    loaded = session.get(Conversation, conv_id)
    assert len(loaded.chat_messages) == 4
    for m in loaded.chat_messages:
        assert loaded.full_text[m.start_offset : m.end_offset] == m.content


def test_save_normalizes_crlf(session):
    conv = save(session, SAMPLE.replace("\n", "\r\n"))

    assert "\r" not in conv.full_text
    assert conv.full_text == SAMPLE
    for m in conv.chat_messages:
        assert conv.full_text[m.start_offset : m.end_offset] == m.content


def test_save_keeps_command_verbatim(session):
    conv = save(session, SAMPLE)

    cmd = "uv run pre-commit run --files tests/test_health.py"
    assert cmd in conv.chat_messages[1].content


def test_save_still_saves_when_warnings_exist(session):
    conv = save(session, "@me: hỏi\n@chat: Dùng:\n```bash\nuv run pytest\n")

    assert count(session, Conversation) == 1
    assert len(conv.chat_messages) == 2


@pytest.mark.parametrize("text", ["", "   \n\n", "không có marker nào"])
def test_save_rejects_text_without_messages(session, text):
    with pytest.raises(NoMessagesError):
        save(session, text)

    assert count(session, Conversation) == 0
    assert count(session, ChatMessage) == 0


def test_save_uses_given_title(session):
    conv = save(session, SAMPLE, title="  Tên tự đặt  ")

    assert conv.title == "Tên tự đặt"


def test_save_blank_title_falls_back_to_auto(session):
    conv = save(session, SAMPLE, title="   ")

    assert conv.title == "Làm sao chạy pre-commit cho một file?"


def test_save_without_me_uses_default_title(session):
    conv = save(session, "@chat: xin chào")

    assert conv.title == DEFAULT_TITLE


# ---------- title ----------

def titles_of(text: str) -> str:
    return make_title(parse(text).messages)


def test_title_truncates_at_60_with_ellipsis():
    title = titles_of("@me: " + "a" * 100)

    assert title == "a" * 60 + "…"


def test_title_exactly_60_is_not_truncated():
    assert titles_of("@me: " + "a" * 60) == "a" * 60


def test_title_flattens_newlines_and_spaces():
    assert titles_of("@me: dòng một\n\n   dòng   hai") == "dòng một dòng hai"


def test_title_uses_first_me_not_later_ones():
    assert titles_of("@chat: x\n@me: đầu tiên\n@me: thứ hai") == "đầu tiên"


def test_title_skips_empty_me():
    assert titles_of("@me:\n@chat: x\n@me: có chữ") == "có chữ"


def test_title_no_trailing_space_before_ellipsis():
    # ký tự thứ 60 là dấu cách: không để "… " dính khoảng trắng
    text = "@me: " + "a" * 59 + " " + "b" * 10
    assert titles_of(text) == "a" * 59 + "…"


# ---------- transaction ----------

def test_save_rolls_back_everything_on_failure(session, monkeypatch):
    real_flush = session.flush

    def failing_commit():
        real_flush()  # dữ liệu đã được ghi vào transaction...
        raise RuntimeError("lỗi giả lập giữa chừng")  # ...rồi hỏng trước khi commit

    monkeypatch.setattr(session, "commit", failing_commit)

    with pytest.raises(RuntimeError):
        save(session, SAMPLE)

    monkeypatch.undo()
    assert count(session, Conversation) == 0
    assert count(session, ChatMessage) == 0