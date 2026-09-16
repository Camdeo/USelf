import enum
import uuid
from datetime import datetime
from sqlalchemy import String, Text, Integer, Boolean, DateTime, ForeignKey, UniqueConstraint, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base

class ParticipantRole(str, enum.Enum):
    creator = "creator"
    partner = "partner"

class ParticipantStatus(str, enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"

class AnswerValue(str, enum.Enum):
    yes = "yes"
    maybe = "maybe"
    no = "no"

class QuizSession(Base):
    __tablename__ = "quiz_sessions"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    status: Mapped[str] = mapped_column(String(20), default="in_progress")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    participants = relationship("Participant", cascade="all, delete-orphan", back_populates="session")
    session_questions = relationship("QuizSessionQuestion", cascade="all, delete-orphan", order_by="QuizSessionQuestion.position")

class Participant(Base):
    __tablename__ = "participants"
    __table_args__ = (UniqueConstraint("quiz_session_id", "role"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    quiz_session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("quiz_sessions.id", ondelete="CASCADE"))
    role: Mapped[ParticipantRole] = mapped_column(Enum(ParticipantRole))
    alias: Mapped[str] = mapped_column(String(50))
    access_token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    status: Mapped[ParticipantStatus] = mapped_column(Enum(ParticipantStatus), default=ParticipantStatus.pending)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    session = relationship("QuizSession", back_populates="participants")
    answers = relationship("Answer", cascade="all, delete-orphan")

class Question(Base):
    __tablename__ = "questions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_id: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    category: Mapped[str] = mapped_column(String(100), index=True)
    block: Mapped[str | None] = mapped_column(String(150), nullable=True)
    text: Mapped[str] = mapped_column(Text)
    direction: Mapped[str | None] = mapped_column(String(50), nullable=True)
    safety_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

class QuizSessionQuestion(Base):
    __tablename__ = "quiz_session_questions"
    __table_args__ = (UniqueConstraint("quiz_session_id", "question_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    quiz_session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("quiz_sessions.id", ondelete="CASCADE"))
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"))
    position: Mapped[int] = mapped_column(Integer)
    text_snapshot: Mapped[str] = mapped_column(Text)
    category_snapshot: Mapped[str] = mapped_column(String(100))
    block_snapshot: Mapped[str | None] = mapped_column(String(150), nullable=True)
    direction_snapshot: Mapped[str | None] = mapped_column(String(50), nullable=True)
    safety_note_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)

class Answer(Base):
    __tablename__ = "answers"
    __table_args__ = (UniqueConstraint("participant_id", "session_question_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    participant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("participants.id", ondelete="CASCADE"))
    session_question_id: Mapped[int] = mapped_column(ForeignKey("quiz_session_questions.id", ondelete="CASCADE"))
    value: Mapped[AnswerValue] = mapped_column(Enum(AnswerValue))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
