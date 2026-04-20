from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ev_monitoring.geofence import is_inside_geofence
from ev_monitoring.models import (
    Booth,
    BoothStatus,
    ChargingSession,
    QueueEntry,
    QueueStatus,
    SessionStatus,
    Station,
    User,
    UserRole,
)


def get_or_create_driver(db: Session, name: str) -> User:
    clean_name = name.strip() or "Demo Driver"
    username = clean_name.lower().replace(" ", "_")
    existing = db.scalar(select(User).where(User.username == username))
    if existing:
        return existing

    driver = User(name=clean_name, username=username, role=UserRole.DRIVER)
    db.add(driver)
    db.commit()
    db.refresh(driver)
    return driver


def create_station(
    db: Session,
    name: str,
    address: str,
    latitude: float,
    longitude: float,
    radius_meters: float,
) -> Station:
    station = Station(
        name=name.strip(),
        address=address.strip(),
        latitude=latitude,
        longitude=longitude,
        radius_meters=radius_meters,
    )
    db.add(station)
    db.commit()
    db.refresh(station)
    return station


def create_booth(
    db: Session,
    station_id: int,
    name: str,
    code: str,
    latitude: float,
    longitude: float,
    radius_meters: float,
) -> Booth:
    booth = Booth(
        station_id=station_id,
        name=name.strip(),
        code=code.strip().upper(),
        latitude=latitude,
        longitude=longitude,
        radius_meters=radius_meters,
        status=BoothStatus.FREE,
    )
    db.add(booth)
    db.commit()
    db.refresh(booth)
    return booth


def attempt_check_in(
    db: Session,
    booth_code: str,
    driver_name: str,
    driver_latitude: float,
    driver_longitude: float,
    start_battery_percent: int,
    target_battery_percent: int,
    current_power_kw: float,
) -> tuple[bool, str, ChargingSession | None]:
    booth = db.scalar(select(Booth).where(Booth.code == booth_code.strip().upper()))
    if booth is None:
        return False, "No booth found for that code.", None
    if booth.status not in {BoothStatus.FREE, BoothStatus.FINISHED}:
        return False, f"{booth.name} is currently {booth.status.value}.", None

    inside, distance = is_inside_geofence(
        booth.latitude,
        booth.longitude,
        driver_latitude,
        driver_longitude,
        booth.radius_meters,
    )
    if not inside:
        return (
            False,
            f"Outside geofence: you are {distance:.1f} m away, radius is {booth.radius_meters:.1f} m.",
            None,
        )

    driver = get_or_create_driver(db, driver_name)
    estimated_minutes = estimate_minutes(
        start_battery_percent,
        target_battery_percent,
        current_power_kw,
    )
    session = ChargingSession(
        booth_id=booth.id,
        driver_id=driver.id,
        driver_latitude=driver_latitude,
        driver_longitude=driver_longitude,
        distance_meters=distance,
        status=SessionStatus.CHARGING,
        start_battery_percent=start_battery_percent,
        target_battery_percent=target_battery_percent,
        current_power_kw=current_power_kw,
        estimated_finish_at=datetime.utcnow() + timedelta(minutes=estimated_minutes),
    )
    booth.status = BoothStatus.CHARGING
    db.add(session)
    db.commit()
    db.refresh(session)
    return True, f"Check-in accepted. Distance from booth: {distance:.1f} m.", session


def estimate_minutes(
    start_battery_percent: int,
    target_battery_percent: int,
    current_power_kw: float,
    assumed_battery_kwh: float = 60.0,
) -> int:
    percent_to_charge = max(target_battery_percent - start_battery_percent, 1)
    energy_needed_kwh = assumed_battery_kwh * (percent_to_charge / 100)
    safe_power_kw = max(current_power_kw, 1)
    return max(round((energy_needed_kwh / safe_power_kw) * 60), 1)


def finish_session(db: Session, session_id: int) -> ChargingSession | None:
    session = db.get(ChargingSession, session_id)
    if session is None:
        return None
    session.status = SessionStatus.FINISHED
    session.finished_at = datetime.utcnow()
    session.booth.status = BoothStatus.FINISHED
    db.commit()
    db.refresh(session)
    return session


def reset_booth(db: Session, booth_id: int) -> Booth | None:
    booth = db.get(Booth, booth_id)
    if booth is None:
        return None
    booth.status = BoothStatus.FREE
    db.commit()
    db.refresh(booth)
    return booth


def join_queue(db: Session, station_id: int, driver_name: str) -> QueueEntry:
    driver = get_or_create_driver(db, driver_name)
    existing = db.scalar(
        select(QueueEntry).where(
            QueueEntry.driver_id == driver.id,
            QueueEntry.station_id == station_id,
            QueueEntry.status == QueueStatus.WAITING,
        )
    )
    if existing:
        return existing
    entry = QueueEntry(station_id=station_id, driver_id=driver.id)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def assign_next_waiting_driver(db: Session, booth_id: int) -> tuple[bool, str]:
    booth = db.get(Booth, booth_id)
    if booth is None:
        return False, "Booth not found."
    if booth.status != BoothStatus.FREE:
        return False, "Booth must be free before assigning a queued driver."

    entry = db.scalar(
        select(QueueEntry)
        .where(
            QueueEntry.station_id == booth.station_id,
            QueueEntry.status == QueueStatus.WAITING,
        )
        .order_by(QueueEntry.requested_at.asc())
    )
    if entry is None:
        return False, "No waiting drivers for this station."

    entry.status = QueueStatus.ASSIGNED
    entry.assigned_booth_id = booth.id
    booth.status = BoothStatus.OCCUPIED
    db.commit()
    return True, f"{entry.driver.name} has been assigned to {booth.name}."


def dashboard_summary(db: Session) -> dict[str, int]:
    total_booths = db.scalar(select(func.count(Booth.id))) or 0
    waiting = db.scalar(
        select(func.count(QueueEntry.id)).where(QueueEntry.status == QueueStatus.WAITING)
    ) or 0
    completed = db.scalar(
        select(func.count(ChargingSession.id)).where(
            ChargingSession.status == SessionStatus.FINISHED
        )
    ) or 0
    active = db.scalar(
        select(func.count(ChargingSession.id)).where(
            ChargingSession.status.in_([SessionStatus.OCCUPIED, SessionStatus.CHARGING])
        )
    ) or 0
    return {
        "total_booths": total_booths,
        "waiting_drivers": waiting,
        "completed_sessions": completed,
        "active_sessions": active,
    }
