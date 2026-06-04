from datetime import datetime

from pydantic import BaseModel


class CategoryBrief(BaseModel):

    id: int

    name: str

    class Config:

        from_attributes = True


class AddressResponse(BaseModel):

    id: int

    street: str

    house: str

    entrance: str | None = None

    apartment: str

    personal_account: str | None = None

    class Config:

        from_attributes = True


class UserBrief(BaseModel):

    id: int

    full_name: str

    email: str | None = None

    role: str | None = None

    class Config:

        from_attributes = True


class TicketMergeHistoryResponse(BaseModel):

    id: int

    primary_ticket_id: int

    secondary_ticket_id: int

    merged_by_user_id: int

    reason: str | None = None

    created_at: datetime

    secondary_ticket_description: str | None = None

    merged_by_name: str | None = None


class TicketCreate(BaseModel):

    description: str

    category_id: int

    address_id: int


class TicketResponse(BaseModel):

    id: int

    description: str

    status: str

    priority: str

    resident_id: int

    category_id: int | None = None

    created_at: datetime | None = None

    subscribers_count: int = 0

    is_creator: bool = False

    is_linked: bool = False

    address: AddressResponse | None = None

    category: CategoryBrief | None = None

    assigned_executor_id: int | None = None

    assigned_executor: UserBrief | None = None

    merge_history: list[TicketMergeHistoryResponse] = []

    class Config:

        from_attributes = True
