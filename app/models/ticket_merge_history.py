from datetime import datetime

from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import Text

from sqlalchemy.orm import relationship

from app.db.database import Base


class TicketMergeHistory(Base):

    __tablename__ = "ticket_merge_history"

    id = Column(Integer, primary_key=True, index=True)

    primary_ticket_id = Column(
        Integer,
        ForeignKey("tickets.id"),
        nullable=False,
        index=True
    )

    secondary_ticket_id = Column(
        Integer,
        ForeignKey("tickets.id"),
        nullable=False,
        index=True
    )

    merged_by_user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    reason = Column(Text, nullable=True)

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    primary_ticket = relationship(
        "Ticket",
        foreign_keys=[primary_ticket_id],
        back_populates="merge_history"
    )

    secondary_ticket = relationship(
        "Ticket",
        foreign_keys=[secondary_ticket_id]
    )

    merged_by = relationship("User")
