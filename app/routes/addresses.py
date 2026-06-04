from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException

from sqlalchemy.orm import Session

from app.db.database import SessionLocal

from app.models.address import Address
from app.models.ticket import Ticket
from app.models.user import User
from app.models.user_address import UserAddress

from app.security.dependencies import (
    get_current_user,
    require_address_reviewer,
    require_resident_addresses,
    STAFF_ROLES,
)


router = APIRouter(
    prefix="/addresses",
    tags=["Addresses"]
)


def get_db():

    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()


def serialize_user_address(link: UserAddress):

    address = link.address

    return {
        "id": link.id,
        "address_id": link.address_id,
        "street": address.street,
        "house": address.house,
        "entrance": address.entrance,
        "apartment": address.apartment,
        "personal_account": address.personal_account,
        "is_primary": link.is_primary,
        "is_verified": link.is_verified,
        "created_at": link.created_at,
        "user": {
            "id": link.user.id,
            "full_name": link.user.full_name,
            "email": link.user.email
        } if link.user else None
    }


def get_user_address_link(
    db: Session,
    link_id: int,
    user_id: int
):

    link = db.query(UserAddress).filter(
        UserAddress.id == link_id,
        UserAddress.user_id == user_id
    ).first()

    if not link:

        raise HTTPException(
            status_code=404,
            detail="Address not found"
        )

    return link


@router.get("/my")
def get_my_addresses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    require_resident_addresses(current_user)

    links = db.query(UserAddress).filter(
        UserAddress.user_id == current_user.id
    ).order_by(
        UserAddress.is_primary.desc(),
        UserAddress.created_at.desc()
    ).all()

    return [
        serialize_user_address(link)
        for link in links
    ]


@router.get("/my/verified")
def get_my_verified_addresses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    require_resident_addresses(current_user)

    links = db.query(UserAddress).filter(
        UserAddress.user_id == current_user.id,
        UserAddress.is_verified == True
    ).order_by(
        UserAddress.is_primary.desc(),
        UserAddress.created_at.desc()
    ).all()

    return [
        serialize_user_address(link)
        for link in links
    ]


@router.post("/my")
def add_my_address(
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    require_resident_addresses(current_user)

    required_fields = [
        "street",
        "house",
        "entrance",
        "apartment",
        "personal_account"
    ]

    for field in required_fields:

        if not data.get(field):

            raise HTTPException(
                status_code=400,
                detail="All address fields are required"
            )

    has_addresses = db.query(UserAddress).filter(
        UserAddress.user_id == current_user.id
    ).first()

    address = Address(
        street=data["street"],
        house=data["house"],
        entrance=data["entrance"],
        apartment=data["apartment"],
        personal_account=data["personal_account"]
    )

    db.add(address)
    db.flush()

    link = UserAddress(
        user_id=current_user.id,
        address_id=address.id,
        is_primary=not bool(has_addresses),
        is_verified=False
    )

    db.add(link)
    db.commit()
    db.refresh(link)

    return serialize_user_address(link)


@router.put("/my/{link_id}")
def update_my_address(
    link_id: int,
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    require_resident_addresses(current_user)

    link = get_user_address_link(
        db,
        link_id,
        current_user.id
    )

    link.address.street = data["street"]
    link.address.house = data["house"]
    link.address.entrance = data["entrance"]
    link.address.apartment = data["apartment"]
    link.address.personal_account = data["personal_account"]
    link.is_verified = False

    db.commit()
    db.refresh(link)

    return serialize_user_address(link)


@router.patch("/my/{link_id}/primary")
def set_primary_address(
    link_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    require_resident_addresses(current_user)

    link = get_user_address_link(
        db,
        link_id,
        current_user.id
    )

    db.query(UserAddress).filter(
        UserAddress.user_id == current_user.id
    ).update({
        UserAddress.is_primary: False
    })

    link.is_primary = True

    db.commit()
    db.refresh(link)

    return serialize_user_address(link)


@router.delete("/my/{link_id}")
def delete_my_address(
    link_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    require_resident_addresses(current_user)

    link = get_user_address_link(
        db,
        link_id,
        current_user.id
    )

    active_ticket = db.query(Ticket).filter(
        Ticket.resident_id == current_user.id,
        Ticket.address_id == link.address_id,
        Ticket.status != "completed"
    ).first()

    if active_ticket:

        raise HTTPException(
            status_code=400,
            detail="Cannot delete address with active tickets"
        )

    db.delete(link)
    db.commit()

    return {
        "message": "Address deleted"
    }


@router.get("/pending")
def get_pending_addresses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    require_address_reviewer(current_user)

    links = db.query(UserAddress).join(
        User,
        UserAddress.user_id == User.id
    ).filter(
        UserAddress.is_verified == False,
        ~User.role.in_(STAFF_ROLES | {"admin"})
    ).order_by(
        UserAddress.created_at.desc()
    ).all()

    return [
        serialize_user_address(link)
        for link in links
    ]


@router.patch("/{link_id}/verify")
def verify_address(
    link_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    require_address_reviewer(current_user)

    link = db.query(UserAddress).filter(
        UserAddress.id == link_id
    ).first()

    if not link:

        raise HTTPException(
            status_code=404,
            detail="Address not found"
        )

    link.is_verified = True

    db.commit()
    db.refresh(link)

    return serialize_user_address(link)
