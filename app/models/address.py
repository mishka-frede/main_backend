from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String

from sqlalchemy.orm import relationship

from app.db.database import Base


class Address(Base):

    __tablename__ = "addresses"

    id = Column(Integer, primary_key=True, index=True)

    street = Column(String(255))

    house = Column(String(50))

    entrance = Column(String(50))

    apartment = Column(String(50))

    personal_account = Column(String(100))

    tickets = relationship(
        "Ticket",
        back_populates="address"
    )

    users = relationship("User")

    user_links = relationship(
        "UserAddress",
        back_populates="address"
    )
