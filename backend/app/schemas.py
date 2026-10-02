from typing import Literal

from pydantic import BaseModel, Field, field_validator


AnswerLiteral = Literal["yes", "maybe", "no"]


class CreateSessionIn(BaseModel):
    creator_alias: str = Field(min_length=1, max_length=50)
    creator_age: int = Field(ge=18, le=99)
    theme_slugs: list[str] = Field(min_length=1, max_length=7)

    @field_validator("creator_alias")
    @classmethod
    def strip_alias(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Имя не может быть пустым")
        return value


class ProfileIn(BaseModel):
    alias: str = Field(min_length=1, max_length=50)
    age: int = Field(ge=18, le=99)

    @field_validator("alias")
    @classmethod
    def strip_alias(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Имя не может быть пустым")
        return value


class ResponseIn(BaseModel):
    session_question_id: int
    value: AnswerLiteral | None = None
    comment: str | None = Field(default=None, max_length=1000)

    @field_validator("comment")
    @classmethod
    def normalize_comment(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class SubmitIn(BaseModel):
    confirm: bool = True
