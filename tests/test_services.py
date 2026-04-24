from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ev_monitoring.models import Base, BoothStatus, QueueStatus
from ev_monitoring.seed import seed_demo_data
from ev_monitoring.services import (
    attempt_check_in,
    estimate_minutes,
    join_queue,
    reset_booth,
)


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    return session_factory()


def test_estimate_minutes_is_positive():
    assert estimate_minutes(20, 80, 22) > 0


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


def test_join_queue_books_driver_if_booth_is_already_free():
    db = make_session()
    seed_demo_data(db)

    entry = join_queue(db, 1, "Queue Driver")

    assert entry.status == QueueStatus.ASSIGNED
    assert entry.assigned_booth_id is not None


def test_booked_driver_can_check_in_and_leave_queue():
    db = make_session()
    seed_demo_data(db)
    entry = join_queue(db, 1, "Queue Driver")

    ok, message, session = attempt_check_in(
        db,
        booth_code="BOOTH-A",
        driver_name="Queue Driver",
        driver_latitude=28.6139,
        driver_longitude=77.2090,
        start_battery_percent=25,
        target_battery_percent=80,
        current_power_kw=22,
    )

    assert entry.status == QueueStatus.CANCELLED
    assert ok is True
    assert "booked booth" in message
    assert session is not None
