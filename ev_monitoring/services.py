from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ev_monitoring.geofence import haversine_distance_meters, is_inside_geofence
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


def normalize_name(value: str) -> str:
    return value.strip() or "Demo Driver"


def get_or_create_driver(db: Session, name: str) -> User:
    clean_name = normalize_name(name)
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
    driver = get_or_create_driver(db, driver_name)

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


def reset_booth(db: Session, booth_id: int) -> tuple[Booth | None, str]:
    booth = db.get(Booth, booth_id)
    if booth is None:
        return None, "Booth not found."
    booth.status = BoothStatus.FREE
    db.commit()
    db.refresh(booth)
    entry = pop_next_waiting_driver(db, booth.station_id)
    if entry is not None:
        return booth, f"{booth.name} is now free. {entry.driver.name} was removed from the queue."
    return booth, f"{booth.name} is now free."


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

    entry.status = QueueStatus.CANCELLED
    db.commit()
    db.refresh(entry)
    return True, f"{entry.driver.name} was removed from the queue for {booth.name}."


def pop_next_waiting_driver(db: Session, station_id: int) -> QueueEntry | None:
    entry = db.scalar(
        select(QueueEntry)
        .where(
            QueueEntry.station_id == station_id,
            QueueEntry.status == QueueStatus.WAITING,
        )
        .order_by(QueueEntry.requested_at.asc())
    )
    if entry is None:
        return None
    entry.status = QueueStatus.CANCELLED
    entry.assigned_booth_id = None
    db.commit()
    db.refresh(entry)
    return entry


def get_driver_queue_entry(
    db: Session,
    driver_name: str,
    station_id: int | None = None,
) -> QueueEntry | None:
    clean_name = normalize_name(driver_name)
    username = clean_name.lower().replace(" ", "_")
    query = (
        select(QueueEntry)
        .join(User)
        .where(
            User.username == username,
            QueueEntry.status == QueueStatus.WAITING,
        )
        .order_by(QueueEntry.requested_at.asc())
    )
    if station_id is not None:
        query = query.where(QueueEntry.station_id == station_id)
    return db.scalar(query)


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


def station_live_status(
    db: Session,
    station: Station,
    *,
    user_latitude: float | None = None,
    user_longitude: float | None = None,
) -> dict[str, float | int | str]:
    booths = list(station.booths)
    free_count = sum(1 for booth in booths if booth.status == BoothStatus.FREE)
    charging_count = sum(1 for booth in booths if booth.status == BoothStatus.CHARGING)
    occupied_count = sum(1 for booth in booths if booth.status == BoothStatus.OCCUPIED)
    finished_count = sum(1 for booth in booths if booth.status == BoothStatus.FINISHED)
    queue_count = db.scalar(
        select(func.count(QueueEntry.id)).where(
            QueueEntry.station_id == station.id,
            QueueEntry.status == QueueStatus.WAITING,
        )
    ) or 0

    distance_meters = None
    if user_latitude is not None and user_longitude is not None:
        distance_meters = haversine_distance_meters(
            user_latitude,
            user_longitude,
            station.latitude,
            station.longitude,
        )

    return {
        "station_id": station.id,
        "station_name": station.name,
        "address": station.address,
        "latitude": station.latitude,
        "longitude": station.longitude,
        "total_booths": len(booths),
        "free_count": free_count,
        "charging_count": charging_count,
        "occupied_count": occupied_count,
        "finished_count": finished_count,
        "queue_count": int(queue_count),
        "distance_meters": distance_meters,
    }


def estimate_energy_kwh(
    start_battery_percent: int,
    target_battery_percent: int,
    battery_kwh: float = 60.0,
) -> float:
    percent_to_charge = max(target_battery_percent - start_battery_percent, 1)
    return round(battery_kwh * (percent_to_charge / 100), 2)


def estimate_payment_amount(
    start_battery_percent: int,
    target_battery_percent: int,
    current_power_kw: float,
    *,
    battery_kwh: float = 60.0,
    energy_rate_per_kwh: float = 14.5,
    power_fee_per_kw: float = 0.35,
) -> dict[str, float]:
    units_kwh = estimate_energy_kwh(
        start_battery_percent,
        target_battery_percent,
        battery_kwh=battery_kwh,
    )
    energy_cost = round(units_kwh * energy_rate_per_kwh, 2)
    power_fee = round(max(current_power_kw, 1) * power_fee_per_kw, 2)
    total_amount = round(energy_cost + power_fee, 2)
    return {
        "units_kwh": units_kwh,
        "energy_cost": energy_cost,
        "power_fee": power_fee,
        "total_amount": total_amount,
    }
