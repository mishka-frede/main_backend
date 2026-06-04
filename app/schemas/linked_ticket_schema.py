from datetime import datetime

from pydantic import BaseModel
from pydantic import Field


class SimilarTicketMatch(BaseModel):

    id: int

    description: str

    status: str

    priority: str

    category_id: int

    category_name: str | None = None

    created_at: datetime

    similarity_score: float

    subscribers_count: int


class CheckSimilarRequest(BaseModel):

    description: str

    category_id: int

    address_id: int


class CheckSimilarResponse(BaseModel):

    similar_found: bool

    matches: list[SimilarTicketMatch] = []


class TicketCreateWithOptions(BaseModel):

    description: str

    category_id: int

    address_id: int

    force_create: bool = False


class TicketJoinRequest(BaseModel):

    description: str | None = None


class TicketSubscriberResponse(BaseModel):

    id: int

    user_id: int

    full_name: str

    joined_at: datetime

    is_creator: bool


class TicketSubscriberDispatcherResponse(TicketSubscriberResponse):

    email: str | None = None


class TicketMergeRequest(BaseModel):

    primary_ticket_id: int

    secondary_ticket_id: int

    reason: str | None = None


class TicketExecutorAssignRequest(BaseModel):

    executor_id: int | None = None


class NotificationResponse(BaseModel):

    id: int

    ticket_id: int | None

    channel: str

    title: str

    message: str

    is_read: bool

    created_at: datetime

    class Config:

        from_attributes = True
