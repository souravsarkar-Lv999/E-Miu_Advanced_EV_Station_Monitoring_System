from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ev_monitoring.models import Booth, Station, User, UserRole
from ev_monitoring.services import create_booth, create_station


def seed_demo_data(db: Session) -> None:
    admin = db.scalar(select(User).where(User.username == "admin"))
    if admin is None:
        admin = User(name="Station Admin", username="admin", role=UserRole.ADMIN)
        db.add(admin)
        db.commit()

    demo_network = [
        {
            "name": "Demo Smart EV Station",
            "address": "Connaught Place charging hub",
            "latitude": 28.6139,
            "longitude": 77.2090,
            "radius_meters": 120,
            "booths": [
                ("Booth A", "BOOTH-A", 28.6139, 77.2090, 60),
                ("Booth B", "BOOTH-B", 28.6141, 77.2092, 60),
                ("Booth C", "BOOTH-C", 28.6137, 77.2088, 60),
            ],
        },
        {
            "name": "Green Circle Fast Charge",
            "address": "India Gate corridor fast charging bay",
            "latitude": 28.6121,
            "longitude": 77.2295,
            "radius_meters": 130,
            "booths": [
                ("Booth D", "BOOTH-D", 28.6121, 77.2295, 60),
                ("Booth E", "BOOTH-E", 28.6123, 77.2298, 60),
            ],
        },
        {
            "name": "Metro Charge Point",
            "address": "Khan Market metro connector station",
            "latitude": 28.6004,
            "longitude": 77.2279,
            "radius_meters": 110,
            "booths": [
                ("Booth F", "BOOTH-F", 28.6004, 77.2279, 60),
                ("Booth G", "BOOTH-G", 28.6006, 77.2282, 60),
            ],
        },
    ]

    for station_data in demo_network:
        station = db.scalar(select(Station).where(Station.name == station_data["name"]))
        if station is None:
            station = create_station(
                db,
                name=station_data["name"],
                address=station_data["address"],
                latitude=station_data["latitude"],
                longitude=station_data["longitude"],
                radius_meters=station_data["radius_meters"],
            )

        for booth_name, booth_code, latitude, longitude, radius in station_data["booths"]:
            existing_booth = db.scalar(select(Booth).where(Booth.code == booth_code))
            if existing_booth is None:
                create_booth(
                    db,
                    station.id,
                    booth_name,
                    booth_code,
                    latitude,
                    longitude,
                    radius,
                )


def reset_demo_data(db: Session) -> None:
    for model in reversed([Station, Booth, User]):
        db.query(model).delete()
    db.commit()
