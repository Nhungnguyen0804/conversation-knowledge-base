"""Service hội thoại: preview (không ghi DB) và save (một transaction).

"""

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models import ChatMessage, Conversation
from app.parser import ParsedMessage, ParseWarning, parse

TITLE_MAX = 60
TITLE_COLUMN_MAX = 200  # khớp String(200) của conversations.title
DEFAULT_TITLE = "Hội thoại chưa đặt tên"


class NoMessagesError(ValueError):
    """Văn bản không có message nào để lưu."""


@dataclass
class PreviewResult:
    suggested_title: str
    message_count: int
    me_count: int
    chat_count: int
    warnings: list[ParseWarning] = field(default_factory=list)


def make_title(messages: list[ParsedMessage]) -> str:
    """Title mặc định: TITLE_MAX ký tự đầu của @me đầu tiên có nội dung."""
    for m in messages:
        if m.role == "me":
            flat = " ".join(m.content.split())
            if not flat:
                continue
            if len(flat) > TITLE_MAX:
                return flat[:TITLE_MAX].rstrip() + "…"
            return flat
    return DEFAULT_TITLE


def preview(text: str) -> PreviewResult:
    """Không ghi DB, không cần session."""
    parsed = parse(text)
    me_count = sum(1 for m in parsed.messages if m.role == "me")
    return PreviewResult(
        suggested_title=make_title(parsed.messages),
        message_count=len(parsed.messages),
        me_count=me_count,
        chat_count=len(parsed.messages) - me_count,
        warnings=parsed.warnings,
    )


def save(session: Session, text: str, title: str | None = None) -> Conversation:
    """Ghi Conversation + ChatMessage trong 1 transaction (commit một lần)."""
    parsed = parse(text)
    if not parsed.messages:
        raise NoMessagesError("Không tìm thấy message nào để lưu.")

    final_title = (title or "").strip() or make_title(parsed.messages)

    conv = Conversation(
        title=final_title[:TITLE_COLUMN_MAX],
        full_text=parsed.normalized_text,
        chat_messages=[
            ChatMessage(
                message_index=i,
                role=m.role,
                content=m.content,
                start_offset=m.start_offset,
                end_offset=m.end_offset,
            )
            for i, m in enumerate(parsed.messages)
        ],
    )
    try:
        session.add(conv)
        session.commit()
    except Exception:
        session.rollback()
        raise
    return conv