import uuid
from datetime import UTC, datetime

from pydantic import EmailStr
from sqlalchemy import DateTime
from sqlmodel import Field, Relationship, SQLModel


def get_datetime_utc() -> datetime:
    return datetime.now(UTC)


# Shared properties
class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


class UserUpdate(SQLModel):
    email: EmailStr | None = Field(default=None, max_length=255)
    is_active: bool | None = None
    is_superuser: bool | None = None
    full_name: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    boxes: list["Box"] = Relationship(
        back_populates="owner",
        sa_relationship_kwargs={"foreign_keys": "Box.owner_id"},
    )
    claimed_box: "Box" = Relationship(
        back_populates="assignee",
        sa_relationship_kwargs={
            "uselist": False,
            "foreign_keys": "Box.assignee_id",
        },
    )
    completed_docs: list["Doc"] = Relationship(back_populates="completed_by")


class UserPublic(UserBase):
    id: uuid.UUID
    created_at: datetime | None = None


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


# --- Box models ---

class BoxBase(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)


class BoxCreate(BoxBase):
    pass


class BoxUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)


class Box(BoxBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", nullable=True, ondelete="SET NULL"
    )
    owner: User | None = Relationship(
        back_populates="boxes", sa_relationship_kwargs={"foreign_keys": "Box.owner_id"}
    )
    assignee_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="user.id",
        nullable=True,
        unique=True,
        ondelete="SET NULL",
    )
    assignee: User | None = Relationship(
        back_populates="claimed_box",
        sa_relationship_kwargs={"foreign_keys": "Box.assignee_id"},
    )
    docs: list["Doc"] = Relationship(back_populates="box", cascade_delete=True)


class BoxPublic(BoxBase):
    id: uuid.UUID
    owner_id: uuid.UUID | None = None
    owner_name: str | None = None
    assignee_id: uuid.UUID | None = None
    assignee_name: str | None = None
    doc_count: int
    total_pages: int
    completed: bool


class BoxesPublic(SQLModel):
    data: list[BoxPublic]
    count: int


# --- Doc models ---

class DocBase(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    completed: bool = Field(default=False)
    pages: int = Field(default=0, ge=0)


class DocCreate(DocBase):
    pass


class DocUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    completed: bool | None = None
    pages: int | None = Field(default=None, ge=0)


class Doc(DocBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    box_id: uuid.UUID = Field(
        foreign_key="box.id", nullable=False, ondelete="CASCADE"
    )
    box: Box | None = Relationship(back_populates="docs")
    completed_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
        nullable=True,
    )
    completed_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", nullable=True, ondelete="SET NULL"
    )
    completed_by: User | None = Relationship(back_populates="completed_docs")


class DocPublic(DocBase):
    id: uuid.UUID
    box_id: uuid.UUID
    completed_at: datetime | None = None
    completed_by_id: uuid.UUID | None = None
    completed_by_name: str | None = None


class DocsPublic(SQLModel):
    data: list[DocPublic]
    count: int


class Message(SQLModel):
    message: str


class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(SQLModel):
    sub: str | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)