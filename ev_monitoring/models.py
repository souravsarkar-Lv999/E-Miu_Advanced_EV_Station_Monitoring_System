from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SqlEnum, Float, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class UserRole(str, Enum):
    ADMIN = "admin"
    DRIVER = "driver"


class BoothStatus(str, Enum):
    FREE = "free"
    OCCUPIED = "occupied"
    CHARGING = "charging"
    FINISHED = "finished"


class SessionStatus(str, Enum):
    OCCUPIED = "occupied"
    CHARGING = "charging"
    FINISHED = "finished"
    CANCELLED = "cancelled"


class QueueStatus(str, Enum):
    WAITING = "waiting"
    ASSIGNED = "assigned"
    CANCELLED = "cancelled"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    username: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    role: Mapped[UserRole] = mapped_column(SqlEnum(UserRole), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    sessions: Mapped[list["ChargingSession"]] = relationship(back_populates="driver")
    queue_entries: Mapped[list["QueueEntry"]] = relationship(back_populates="driver")


class Station(Base):
    __tablename__ = "stations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    address: Mapped[str] = mapped_column(String(250), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    radius_meters: Mapped[float] = mapped_column(Float, default=100)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    booths: Mapped[list["Booth"]] = relationship(back_populates="station")


class Booth(Base):
    __tablename__ = "booths"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    code: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    radius_meters: Mapped[float] = mapped_column(Float, default=50)
    status: Mapped[BoothStatus] = mapped_column(
        SqlEnum(BoothStatus), default=BoothStatus.FREE, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    station: Mapped[Station] = relationship(back_populates="booths")
    sessions: Mapped[list["ChargingSession"]] = relationship(back_populates="booth")


class ChargingSession(Base):
    __tablename__ = "charging_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    booth_id: Mapped[int] = mapped_column(ForeignKey("booths.id"), nullable=False)
    driver_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    driver_latitude: Mapped[float] = mapped_column(Float, nullable=False)
    driver_longitude: Mapped[float] = mapped_column(Float, nullable=False)
    distance_meters: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[SessionStatus] = mapped_column(
        SqlEnum(SessionStatus), default=SessionStatus.OCCUPIED, nullable=False
    )
    start_battery_percent: Mapped[int] = mapped_column(Integer, default=20)
    target_battery_percent: Mapped[int] = mapped_column(Integer, default=80)
    current_power_kw: Mapped[float] = mapped_column(Float, default=22.0)
    estimated_finish_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    booth: Mapped[Booth] = relationship(back_populates="sessions")
    driver: Mapped[User] = relationship(back_populates="sessions")


class QueueEntry(Base):
    __tablename__ = "queue_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"), nullable=False)
    driver_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[QueueStatus] = mapped_column(
        SqlEnum(QueueStatus), default=QueueStatus.WAITING, nullable=False
    )
    requested_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    assigned_booth_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    station: Mapped[Station] = relationship()
    driver: Mapped[User] = relationship(back_populates="queue_entries")
