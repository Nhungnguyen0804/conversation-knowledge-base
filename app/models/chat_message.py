from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdTimestampMixin

if TYPE_CHECKING:
    from app.models.conversation import Conversation


class ChatMessage(IdTimestampMixin, Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        UniqueConstraint(
            "conversation_id", "message_index", name="uq_chat_message_conv_index"
        ),
    )

    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    message_index: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(10))  # "me" | "chat"
    content: Mapped[str] = mapped_column(Text)
    start_offset: Mapped[int] = mapped_column(Integer)
    end_offset: Mapped[int] = mapped_column(Integer)

    conversation: Mapped["Conversation"] = relationship(
        back_populates="chat_messages"
    )
