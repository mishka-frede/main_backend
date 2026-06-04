from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException

from fastapi.security import OAuth2PasswordRequestForm

from sqlalchemy.orm import Session

from app.db.database import SessionLocal

from app.models.user import User
from app.models.address import Address
from app.models.role import Role
from app.models.user_address import UserAddress

from app.schemas.user_schema import UserCreate

from app.security.hashing import hash_password
from app.security.hashing import verify_password

from app.security.jwt_handler import create_access_token


router = APIRouter(
    prefix="/auth",
    tags=["Auth"]
)


def get_db():

    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()


@router.post("/register")
def register(
    user: UserCreate,
    db: Session = Depends(get_db)
):

    existing_user = db.query(User).filter(
        User.email == user.email
    ).first()

    if existing_user:

        raise HTTPException(
            status_code=400,
            detail="Email already exists"
        )

    if not user.personal_data_consent:

        raise HTTPException(
            status_code=400,
            detail="Personal data processing consent is required"
        )

    role = db.query(Role).filter(
        Role.code == user.role
    ).first()

    if not role:

        raise HTTPException(
            status_code=400,
            detail="Invalid role"
        )

    hashed_password = hash_password(
        user.password[:72]
    )

    address = Address(
        street=user.street,
        house=user.house,
        entrance=user.entrance,
        apartment=user.apartment,
        personal_account=user.personal_account
    )

    db.add(address)

    db.flush()

    new_user = User(
        full_name=user.full_name,
        email=user.email,
        phone=user.phone,
        password_hash=hashed_password,
        role=user.role
    )

    db.add(new_user)

    db.flush()

    user_address = UserAddress(
        user_id=new_user.id,
        address_id=address.id,
        is_primary=True,
        is_verified=False
    )

    db.add(user_address)

    db.commit()

    db.refresh(new_user)

    return {
        "message": "User created"
    }


@router.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):

    db_user = db.query(User).filter(
        User.email == form_data.username
    ).first()

    if not db_user:

        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )

    valid_password = verify_password(
        form_data.password[:72],
        db_user.password_hash
    )

    if not valid_password:

        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )

    access_token = create_access_token(
        data={
            "sub": str(db_user.id),
            "email": db_user.email,
            "role": db_user.role
        }
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": db_user.role
    }
