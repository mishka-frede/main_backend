from pydantic import BaseModel
from pydantic import EmailStr
from pydantic import Field
from pydantic import field_validator


class UserCreate(BaseModel):

    full_name: str

    email: EmailStr

    phone: str

    password: str = Field(
        min_length=5,
        max_length=72
    )

    street: str

    house: str

    entrance: str

    apartment: str

    personal_account: str

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


class StaffUserCreate(BaseModel):

    full_name: str

    email: EmailStr

    phone: str = ""

    password: str = Field(
        min_length=5,
        max_length=72
    )

    role: str = Field(
        ...,
        description="dispatcher | executor"
    )


class UserLogin(BaseModel):

    email: EmailStr

    password: str = Field(
        min_length=5,
        max_length=72
    )
