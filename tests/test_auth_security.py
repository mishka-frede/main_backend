import os
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

from app.routes import auth
from app.schemas.user_schema import UserCreate
from app.schemas.user_schema import UserLogin


def request_from(host: str):

    return SimpleNamespace(
        client=SimpleNamespace(host=host)
    )


def test_public_registration_requires_resident_role():

    with pytest.raises(ValidationError):
        UserCreate(
            full_name="Resident User",
            email="resident@example.com",
            phone="+79990000000",
            password="Password1",
            street="Main Street",
            house="10",
            entrance="1",
            apartment="7",
            personal_account="PA-100",
            role="admin",
            personal_data_consent=True
        )


def test_registration_normalizes_email_and_text_fields():

    user = UserCreate(
        full_name="  Resident User  ",
        email="Resident@Example.COM",
        phone=" +79990000000 ",
        password="Password1",
        street=" Main Street ",
        house=" 10 ",
        entrance=" 1 ",
        apartment=" 7 ",
        personal_account=" PA-100 ",
        personal_data_consent=True
    )

    assert user.email == "resident@example.com"
    assert user.full_name == "Resident User"
    assert user.street == "Main Street"
    assert user.personal_account == "PA-100"


def test_password_policy_requires_letter_and_digit():

    with pytest.raises(ValidationError):
        UserCreate(
            full_name="Resident User",
            email="resident@example.com",
            phone="+79990000000",
            password="password",
            street="Main Street",
            house="10",
            entrance="1",
            apartment="7",
            personal_account="PA-100",
            personal_data_consent=True
        )


def test_login_validation_normalizes_email():

    login = UserLogin(
        email="Resident@Example.COM",
        password="Password1"
    )

    assert login.email == "resident@example.com"


def test_login_rate_limit_blocks_after_failed_attempts():

    auth._login_attempts.clear()

    request = request_from("127.0.0.1")
    email = "resident@example.com"

    for _ in range(auth.LOGIN_RATE_LIMIT_ATTEMPTS):
        auth.ensure_login_not_rate_limited(request, email)
        auth.register_failed_login(request, email)

    with pytest.raises(HTTPException) as exc:
        auth.ensure_login_not_rate_limited(request, email)

    assert exc.value.status_code == 429

    auth.clear_failed_logins(request, email)
    auth.ensure_login_not_rate_limited(request, email)
