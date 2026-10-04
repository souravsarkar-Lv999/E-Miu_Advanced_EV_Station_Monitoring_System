from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ev_monitoring.models import Base, BoothStatus, QueueStatus
from ev_monitoring.seed import seed_demo_data
from ev_monitoring.services import (
    attempt_check_in,
    estimate_minutes,
    estimate_payment_amount,
    join_queue,
    reset_booth,
    station_live_status,
)


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    return session_factory()


def test_estimate_minutes_is_positive():
    assert estimate_minutes(20, 80, 22) > 0


def test_estimate_minutes_changes_with_battery_size():
    small_pack = estimate_minutes(20, 80, 22, assumed_battery_kwh=40)
    large_pack = estimate_minutes(20, 80, 22, assumed_battery_kwh=80)

    assert large_pack > small_pack


def test_check_in_accepts_inside_geofence():
    db = make_session()
    seed_demo_data(db)

    ok, message, session = attempt_check_in(
        db,
        booth_code="BOOTH-A",
        driver_name="Asha Driver",
        driver_latitude=28.6139,
        driver_longitude=77.2090,
        start_battery_percent=25,
        target_battery_percent=80,
        current_power_kw=22,
    )

    assert ok is True
    assert "accepted" in message
    assert session is not None
    assert session.booth.status == BoothStatus.CHARGING


def test_check_in_rejects_outside_geofence():
    db = make_session()
    seed_demo_data(db)

    ok, message, session = attempt_check_in(
        db,
        booth_code="BOOTH-A",
        driver_name="Far Driver",
        driver_latitude=28.7041,
        driver_longitude=77.1025,
        start_battery_percent=25,
        target_battery_percent=80,
        current_power_kw=22,
    )

    assert ok is False
    assert "Outside geofence" in message
    assert session is None


def test_reset_booth_sets_it_free_after_session():
    db = make_session()
    seed_demo_data(db)
    ok, _, session = attempt_check_in(
        db, "BOOTH-A", "Asha Driver", 28.6139, 77.2090, 25, 80, 22
    )

    assert ok is True
    booth, message = reset_booth(db, session.booth_id)

    assert booth.status == BoothStatus.FREE
    assert "now free" in message


def test_join_queue_keeps_driver_waiting():
    db = make_session()
    seed_demo_data(db)

    entry = join_queue(db, 1, "Queue Driver")

    assert entry.status == QueueStatus.WAITING
    assert entry.assigned_booth_id is None


def test_reset_booth_removes_first_waiting_driver_from_queue():
    db = make_session()
    seed_demo_data(db)
    join_queue(db, 1, "Queue Driver")
    ok, _, session = attempt_check_in(
        db, "BOOTH-A", "Asha Driver", 28.6139, 77.2090, 25, 80, 22
    )

    assert ok is True
    booth, message = reset_booth(db, session.booth_id)
    remaining = join_queue(db, 1, "Queue Driver")

    assert booth.status == BoothStatus.FREE
    assert "removed from the queue" in message
    assert remaining.status == QueueStatus.WAITING


def test_station_live_status_counts_booths_and_queue():
    db = make_session()
    seed_demo_data(db)
    join_queue(db, 1, "Queue Driver")
    ok, _, session = attempt_check_in(
        db, "BOOTH-A", "Asha Driver", 28.6139, 77.2090, 25, 80, 22
    )

    assert ok is True

    snapshot = station_live_status(db, session.booth.station, user_latitude=28.6139, user_longitude=77.2090)

    assert snapshot["charging_count"] == 1
    assert snapshot["free_count"] >= 1
    assert snapshot["queue_count"] == 1
    assert snapshot["distance_meters"] == 0


def test_estimate_payment_amount_uses_units_and_power():
    quote = estimate_payment_amount(20, 80, 30)

    assert quote["units_kwh"] == 36.0
    assert quote["energy_cost"] == 522.0
    assert quote["power_fee"] == 10.5
    assert quote["total_amount"] == 532.5
