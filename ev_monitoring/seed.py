from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ev_monitoring.models import Booth, Station, User, UserRole
from ev_monitoring.services import create_booth, create_station


def seed_demo_data(db: Session) -> None:
    if db.scalar(select(Station)):
        return

    admin = User(name="Station Admin", username="admin", role=UserRole.ADMIN)
    db.add(admin)
    db.commit()

    station = create_station(
        db,
        name="Demo Smart EV Station",
        address="Sample city charging hub",
        latitude=28.6139,
        longitude=77.2090,
        radius_meters=120,
    )
    create_booth(db, station.id, "Booth A", "BOOTH-A", 28.6139, 77.2090, 60)
    create_booth(db, station.id, "Booth B", "BOOTH-B", 28.6141, 77.2092, 60)
    create_booth(db, station.id, "Booth C", "BOOTH-C", 28.6137, 77.2088, 60)


def reset_demo_data(db: Session) -> None:
    for model in reversed([Station, Booth, User]):
        db.query(model).delete()
    db.commit()
