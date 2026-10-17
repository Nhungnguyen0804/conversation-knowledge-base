from typing import TYPE_CHECKING

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdTimestampMixin

if TYPE_CHECKING:
    from app.models.chat_message import ChatMessage


class Conversation(IdTimestampMixin, Base):
    __tablename__ = "conversations"

    title: Mapped[str] = mapped_column(String(200))
    full_text: Mapped[str] = mapped_column(Text)

    chat_messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ChatMessage.message_index",
    )
