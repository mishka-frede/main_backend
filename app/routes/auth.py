from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Request

from fastapi.security import OAuth2PasswordRequestForm

from collections import defaultdict
from time import monotonic
import os

from sqlalchemy.orm import Session

from app.db.database import SessionLocal

from app.models.user import User
from app.models.address import Address
from app.models.role import Role
from app.models.user_address import UserAddress

from app.schemas.user_schema import UserCreate
from app.schemas.user_schema import UserLogin

from app.security.hashing import hash_password
from app.security.hashing import verify_password

from app.security.jwt_handler import create_access_token


router = APIRouter(
    prefix="/auth",
    tags=["Auth"]
)

LOGIN_RATE_LIMIT_ATTEMPTS = int(
    os.getenv("LOGIN_RATE_LIMIT_ATTEMPTS", "5")
)

LOGIN_RATE_LIMIT_WINDOW_SECONDS = int(
    os.getenv("LOGIN_RATE_LIMIT_WINDOW_SECONDS", "60")
)

_login_attempts = defaultdict(list)


def get_db():

    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()


def _login_rate_key(request: Request, email: str) -> str:

    client_host = request.client.host if request.client else "unknown"

    return f"{client_host}:{email.lower()}"


def _prune_attempts(key: str, now: float):

    window_started_at = now - LOGIN_RATE_LIMIT_WINDOW_SECONDS

    _login_attempts[key] = [
        attempt_at
        for attempt_at in _login_attempts[key]
        if attempt_at >= window_started_at
    ]


def ensure_login_not_rate_limited(request: Request, email: str):

    now = monotonic()
    key = _login_rate_key(request, email)

    _prune_attempts(key, now)

    if len(_login_attempts[key]) >= LOGIN_RATE_LIMIT_ATTEMPTS:

        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Try again later."
        )


def register_failed_login(request: Request, email: str):

    now = monotonic()
    key = _login_rate_key(request, email)

    _prune_attempts(key, now)
    _login_attempts[key].append(now)


def clear_failed_logins(request: Request, email: str):

    key = _login_rate_key(request, email)

    _login_attempts.pop(key, None)


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
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):

    try:

        login_data = UserLogin(
            email=form_data.username,
            password=form_data.password
        )

    except ValueError:

        raise HTTPException(
            status_code=422,
            detail="Invalid login data"
        )

    ensure_login_not_rate_limited(request, login_data.email)

    db_user = db.query(User).filter(
        User.email == login_data.email
    ).first()

    if not db_user:

        register_failed_login(request, login_data.email)

        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )

    valid_password = verify_password(
        login_data.password[:72],
        db_user.password_hash
    )

    if not valid_password:

        register_failed_login(request, login_data.email)

        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )

    clear_failed_logins(request, login_data.email)

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
