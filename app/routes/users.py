from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException

from sqlalchemy.orm import Session

from app.db.database import get_db

from app.models.user import User
from app.models.role import Role
from app.models.user_address import UserAddress

from app.schemas.user_schema import StaffUserCreate

from app.security.dependencies import (
    get_current_user,
    require_admin,
    STAFF_ROLES,
)

from app.security.hashing import (
    hash_password
)

from app.services.user_roles import (
    clear_user_addresses,
    is_staff_role,
)


router = APIRouter(
    prefix="/users",
    tags=["Users"]
)


@router.get("/")
def get_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    )
):

    require_admin(current_user)

    users = db.query(User).order_by(
        User.id
    ).all()

    return [
        {
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "phone": user.phone,
            "role": user.role,
            "role_name": user.role_info.name if user.role_info else user.role,
            "is_active": user.is_active,
            "is_current": user.id == current_user.id,
            "is_staff": user.role in STAFF_ROLES
        }
        for user in users
    ]


@router.get("/staff")
def get_staff_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    require_admin(current_user)

    users = db.query(User).filter(
        User.role.in_(STAFF_ROLES)
    ).order_by(
        User.role,
        User.full_name
    ).all()

    return [
        {
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "phone": user.phone,
            "role": user.role,
            "role_name": user.role_info.name if user.role_info else user.role,
            "is_active": user.is_active
        }
        for user in users
    ]


@router.get("/executors")
def get_executor_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    if current_user.role not in {"admin", "dispatcher"}:

        raise HTTPException(
            status_code=403,
            detail="Access denied"
        )

    users = db.query(User).filter(
        User.role == "executor",
        User.is_active == True
    ).order_by(
        User.full_name
    ).all()

    return [
        {
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "phone": user.phone,
            "role": user.role
        }
        for user in users
    ]


@router.post("/staff")
def create_staff_user(
    data: StaffUserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    require_admin(current_user)

    if data.role not in STAFF_ROLES:

        raise HTTPException(
            status_code=400,
            detail="Role must be dispatcher or executor"
        )

    existing_user = db.query(User).filter(
        User.email == data.email
    ).first()

    if existing_user:

        raise HTTPException(
            status_code=400,
            detail="Email already exists"
        )

    role = db.query(Role).filter(
        Role.code == data.role
    ).first()

    if not role:

        raise HTTPException(
            status_code=400,
            detail="Invalid role"
        )

    new_user = User(
        full_name=data.full_name,
        email=data.email,
        phone=data.phone,
        password_hash=hash_password(data.password[:72]),
        role=data.role
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "message": "Staff user created",
        "id": new_user.id,
        "role": new_user.role
    }


@router.get("/roles")
def get_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    )
):

    require_admin(current_user)

    roles = db.query(Role).order_by(
        Role.name
    ).all()

    return [
        {
            "code": role.code,
            "name": role.name
        }
        for role in roles
    ]


@router.patch("/{user_id}/role")
def update_user_role(
    user_id: int,
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    )
):

    require_admin(current_user)

    if user_id == current_user.id:

        raise HTTPException(
            status_code=400,
            detail="Cannot change your own role"
        )

    role_code = data.get("role")

    role = db.query(Role).filter(
        Role.code == role_code
    ).first()

    if not role:

        raise HTTPException(
            status_code=400,
            detail="Invalid role"
        )

    if role_code in STAFF_ROLES:

        raise HTTPException(
            status_code=400,
            detail="Use staff tab to create dispatcher or executor"
        )

    if role_code != "resident":

        raise HTTPException(
            status_code=400,
            detail="Only resident role can be assigned here"
        )

    user = db.query(User).filter(
        User.id == user_id
    ).first()

    if not user:

        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    if user.role == "admin":

        raise HTTPException(
            status_code=400,
            detail="Cannot change admin role"
        )

    if is_staff_role(user.role):
        clear_user_addresses(db, user.id)

    user.role = role.code

    db.commit()

    return {
        "message": "Role updated"
    }


@router.get("/me")
def get_profile(
    current_user: User = Depends(
        get_current_user
    )
):

    primary_link = next(
        (
            link
            for link in current_user.address_links
            if link.is_primary
        ),
        None
    )

    address = primary_link.address if primary_link else None

    return {
        "id": current_user.id,
        "full_name":
            current_user.full_name,
        "email":
            current_user.email,
        "phone":
            current_user.phone,
        "role": current_user.role,
        "has_addresses": current_user.role == "resident",
        "street":
            address.street if address else "",
        "house":
            address.house if address else "",
        "entrance":
            address.entrance if address else "",
        "apartment":
            address.apartment if address else ""
    }


@router.put("/me")
def update_profile(
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    )
):

    user = db.query(User).filter(
        User.id == current_user.id
    ).first()

    if not user:

        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    existing_user = db.query(User).filter(
        User.email == data["email"],
        User.id != user.id
    ).first()

    if existing_user:

        raise HTTPException(
            status_code=400,
            detail="Email already exists"
        )

    user.full_name = (
        data["full_name"]
    )

    user.email = (
        data["email"]
    )

    user.phone = (
        data["phone"]
    )

    if data.get("password"):

        user.password_hash = (
            hash_password(
                data["password"]
            )
        )

    db.commit()

    return {
        "message":
            "Profile updated"
    }
