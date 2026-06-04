from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey

from sqlalchemy.orm import relationship

from datetime import datetime

from app.db.database import Base


class Ticket(Base):

    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)

    description = Column(Text, nullable=False)

    status = Column(String(50), default="new")

    priority = Column(String(50), default="medium")

    created_at = Column(DateTime, default=datetime.utcnow)

    resident_id = Column(
        Integer,
        ForeignKey("users.id")
    )

    category_id = Column(
        Integer,
        ForeignKey("categories.id")
    )

    address_id = Column(
        Integer,
        ForeignKey("addresses.id")
    )

    merged_into_id = Column(
        Integer,
        ForeignKey("tickets.id"),
        nullable=True
    )

    assigned_executor_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True
    )

    completed_at = Column(DateTime, nullable=True)

    address = relationship(
        "Address",
        back_populates="tickets"
    )

    resident = relationship(
        "User",
        foreign_keys=[resident_id]
    )

    assigned_executor = relationship(
        "User",
        foreign_keys=[assigned_executor_id]
    )

    category = relationship("Category")

    links = relationship(
        "TicketLink",
        back_populates="ticket",
        cascade="all, delete-orphan"
    )

    feedback_entries = relationship(
        "TicketFeedback",
        back_populates="ticket",
        cascade="all, delete-orphan"
    )

    merge_history = relationship(
        "TicketMergeHistory",
        foreign_keys="TicketMergeHistory.primary_ticket_id",
        back_populates="primary_ticket",
        cascade="all, delete-orphan"
    )
