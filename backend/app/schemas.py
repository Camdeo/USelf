from pydantic import BaseModel, Field
from typing import Literal

AnswerLiteral = Literal["yes", "maybe", "no"]

class CreateSessionIn(BaseModel):
    creator_alias: str = Field(default="Я", min_length=1, max_length=50)
    partner_alias: str = Field(default="Партнёр", min_length=1, max_length=50)

class AnswerIn(BaseModel):
    session_question_id: int
    value: AnswerLiteral

class SubmitIn(BaseModel):
    confirm: bool = True
