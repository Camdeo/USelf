from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class QuizSession(Base):
    __tablename__ = "quiz_sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status: Mapped[str] = mapped_column(String(20), default="in_progress", nullable=False)
    theme_slugs_json: Mapped[str] = mapped_column(Text, nullable=False)
    question_bank_version: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    participants = relationship("Participant", back_populates="session", cascade="all, delete-orphan")
    questions = relationship(
        "QuizSessionQuestion",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="QuizSessionQuestion.position",
    )


class Participant(Base):
    __tablename__ = "participants"
    __table_args__ = (UniqueConstraint("quiz_session_id", "role", name="uq_participant_role"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    quiz_session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("quiz_sessions.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # creator | partner
    alias: Mapped[str | None] = mapped_column(String(50), nullable=True)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    profile_complete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    access_token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    session = relationship("QuizSession", back_populates="participants")
    responses = relationship("Response", back_populates="participant", cascade="all, delete-orphan")


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    bank_order: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    theme_slug: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    theme_title: Mapped[str] = mapped_column(String(120), nullable=False)
    block_id: Mapped[str] = mapped_column(String(80), nullable=False)
    block_title: Mapped[str] = mapped_column(String(160), nullable=False)
    block_intro: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    side_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    side_label: Mapped[str | None] = mapped_column(String(80), nullable=True)
    attention_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    attention_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    knowledge_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)
    review_flag: Mapped[str | None] = mapped_column(String(80), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class QuizSessionQuestion(Base):
    __tablename__ = "quiz_session_questions"
    __table_args__ = (
        UniqueConstraint("quiz_session_id", "question_id", name="uq_session_question"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    quiz_session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("quiz_sessions.id", ondelete="CASCADE"), nullable=False
    )
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    external_id_snapshot: Mapped[str] = mapped_column(String(64), nullable=False)
    theme_slug_snapshot: Mapped[str] = mapped_column(String(50), nullable=False)
    theme_title_snapshot: Mapped[str] = mapped_column(String(120), nullable=False)
    block_id_snapshot: Mapped[str] = mapped_column(String(80), nullable=False)
    block_title_snapshot: Mapped[str] = mapped_column(String(160), nullable=False)
    block_intro_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    text_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    side_label_snapshot: Mapped[str | None] = mapped_column(String(80), nullable=True)
    attention_note_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_flag_snapshot: Mapped[str | None] = mapped_column(String(80), nullable=True)

    session = relationship("QuizSession", back_populates="questions")
    responses = relationship("Response", back_populates="session_question", cascade="all, delete-orphan")


class Response(Base):
    __tablename__ = "responses"
    __table_args__ = (
        UniqueConstraint("participant_id", "session_question_id", name="uq_participant_response"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    participant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("participants.id", ondelete="CASCADE"), nullable=False
    )
    session_question_id: Mapped[int] = mapped_column(
        ForeignKey("quiz_session_questions.id", ondelete="CASCADE"), nullable=False
    )
    value: Mapped[str | None] = mapped_column(String(10), nullable=True)  # yes | maybe | no | NULL
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    participant = relationship("Participant", back_populates="responses")
    session_question = relationship("QuizSessionQuestion", back_populates="responses")
