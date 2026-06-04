from pydantic import BaseModel


class CommentCreate(BaseModel):

    text: str


class CommentResponse(BaseModel):

    id: int

    text: str

    user_id: int

    author_name: str | None = None

    author_role: str | None = None

    class Config:

        from_attributes = True
