from pydantic import BaseModel
from pydantic import EmailStr
from pydantic import Field
from pydantic import field_validator
from pydantic import model_validator


def validate_password_strength(value: str) -> str:

    if len(value) < 8:

        raise ValueError(
            "Password must contain at least 8 characters"
        )

    if not any(char.isalpha() for char in value):

        raise ValueError(
            "Password must contain at least one letter"
        )

    if not any(char.isdigit() for char in value):

        raise ValueError(
            "Password must contain at least one digit"
        )

    if value.strip() != value:

        raise ValueError(
            "Password must not start or end with spaces"
        )

    return value


def normalize_text(value: str) -> str:

    return value.strip()


class UserCreate(BaseModel):

    full_name: str = Field(
        min_length=2,
        max_length=255
    )

    email: EmailStr

    phone: str = Field(
        min_length=5,
        max_length=50
    )

    password: str = Field(
        min_length=8,
        max_length=72
    )

    street: str = Field(
        min_length=2,
        max_length=255
    )

    house: str = Field(
        min_length=1,
        max_length=50
    )

    entrance: str = Field(
        min_length=1,
        max_length=50
    )

    apartment: str = Field(
        min_length=1,
        max_length=50
    )

    personal_account: str = Field(
        min_length=3,
        max_length=100
    )

    role: str = "resident"

    personal_data_consent: bool = False

    @field_validator("personal_data_consent")
    @classmethod
    def consent_must_be_given(cls, value: bool) -> bool:

        if not value:

            raise ValueError(
                "Personal data processing consent is required"
        )

        return value

    @field_validator("email", mode="after")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> EmailStr:

        return str(value).lower()

    @field_validator(
        "full_name",
        "phone",
        "street",
        "house",
        "entrance",
        "apartment",
        "personal_account",
        mode="before"
    )
    @classmethod
    def strip_text_fields(cls, value: str) -> str:

        if isinstance(value, str):
            return normalize_text(value)

        return value

    @field_validator("password")
    @classmethod
    def password_must_be_strong(cls, value: str) -> str:

        return validate_password_strength(value)

    @field_validator("role")
    @classmethod
    def public_registration_is_resident_only(cls, value: str) -> str:

        if value != "resident":

            raise ValueError(
                "Public registration is available only for resident role"
            )

        return value


class StaffUserCreate(BaseModel):

    full_name: str = Field(
        min_length=2,
        max_length=255
    )

    email: EmailStr

    phone: str = Field(
        default="",
        max_length=50
    )

    password: str = Field(
        min_length=8,
        max_length=72
    )

    role: str = Field(
        ...,
        description="dispatcher | executor"
    )

    @field_validator("email", mode="after")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> EmailStr:

        return str(value).lower()

    @field_validator("full_name", "phone", "role", mode="before")
    @classmethod
    def strip_text_fields(cls, value: str) -> str:

        if isinstance(value, str):
            return normalize_text(value)

        return value

    @field_validator("password")
    @classmethod
    def password_must_be_strong(cls, value: str) -> str:

        return validate_password_strength(value)


class UserLogin(BaseModel):

    email: EmailStr

    password: str = Field(
        min_length=8,
        max_length=72
    )

    @model_validator(mode="after")
    def normalize_login(self):

        self.email = str(self.email).lower()

        return self

    @field_validator("password")
    @classmethod
    def password_must_not_be_blank(cls, value: str) -> str:

        if not value.strip():

            raise ValueError("Password is required")

        return value
