from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(120), default="Student")
    target_sleep_hours: Mapped[float] = mapped_column(Float, default=8.0)
    entries: Mapped[list["SleepEntry"]] = relationship(back_populates="profile", cascade="all, delete-orphan")
    user: Mapped["User | None"] = relationship(back_populates="profile")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    profile: Mapped[Profile | None] = relationship(back_populates="user", uselist=False)


class SessionToken(Base):
    __tablename__ = "session_tokens"

    token: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RecommendationProgress(Base):
    __tablename__ = "recommendation_progress"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    completed: Mapped[bool] = mapped_column(Boolean, default=False)


class SleepEntry(Base):
    __tablename__ = "sleep_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"), index=True)
    entry_date: Mapped[date] = mapped_column(Date, index=True)
    bedtime: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    wake_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sleep_quality: Mapped[int] = mapped_column(Integer)
    caffeine_mg: Mapped[int] = mapped_column(Integer, default=0)
    screen_minutes: Mapped[int] = mapped_column(Integer, default=0)
    activity_minutes: Mapped[int] = mapped_column(Integer, default=0)
    mood: Mapped[int] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    profile: Mapped[Profile] = relationship(back_populates="entries")
