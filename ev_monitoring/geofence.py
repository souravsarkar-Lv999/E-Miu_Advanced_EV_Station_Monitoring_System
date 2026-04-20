from __future__ import annotations

from math import asin, cos, radians, sin, sqrt


EARTH_RADIUS_METERS = 6_371_000


def haversine_distance_meters(
    origin_latitude: float,
    origin_longitude: float,
    target_latitude: float,
    target_longitude: float,
) -> float:
    """Return distance between two GPS points in meters."""
    origin_lat = radians(origin_latitude)
    target_lat = radians(target_latitude)
    delta_lat = radians(target_latitude - origin_latitude)
    delta_lon = radians(target_longitude - origin_longitude)

    a = (
        sin(delta_lat / 2) ** 2
        + cos(origin_lat) * cos(target_lat) * sin(delta_lon / 2) ** 2
    )
    c = 2 * asin(sqrt(a))
    return EARTH_RADIUS_METERS * c


def is_inside_geofence(
    booth_latitude: float,
    booth_longitude: float,
    driver_latitude: float,
    driver_longitude: float,
    radius_meters: float,
) -> tuple[bool, float]:
    """Check whether a driver is inside a booth's geofence."""
    distance = haversine_distance_meters(
        booth_latitude,
        booth_longitude,
        driver_latitude,
        driver_longitude,
    )
    return distance <= radius_meters, distance

