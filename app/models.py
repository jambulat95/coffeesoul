from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(AsyncAttrs, DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    full_name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20))
    shop_id: Mapped[str] = mapped_column(String(50))
    position: Mapped[str] = mapped_column(String(50))


class Checklist(Base):
    __tablename__ = "checklists"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(100))
    shop_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    target_position: Mapped[str | None] = mapped_column(String(50), nullable=True)

    questions = relationship(
        "Question",
        back_populates="checklist",
        cascade="all, delete",
    )


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    checklist_id: Mapped[int] = mapped_column(ForeignKey("checklists.id"))
    text: Mapped[str] = mapped_column(String(255))
    type: Mapped[str] = mapped_column(String(20))
    needs_photo: Mapped[bool] = mapped_column(Boolean, default=False)

    checklist = relationship("Checklist", back_populates="questions")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    checklist_id: Mapped[int] = mapped_column(ForeignKey("checklists.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    score_percent: Mapped[int] = mapped_column(Integer, default=0)


class Answer(Base):
    __tablename__ = "answers"

    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id"))
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"))
    answer_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    photo_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    points: Mapped[int] = mapped_column(Integer, default=0)
