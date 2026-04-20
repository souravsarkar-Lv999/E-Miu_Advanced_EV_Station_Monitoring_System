from ev_monitoring.geofence import haversine_distance_meters, is_inside_geofence


def test_same_point_is_inside_geofence():
    inside, distance = is_inside_geofence(28.6139, 77.2090, 28.6139, 77.2090, 50)

    assert inside is True
    assert distance == 0


def test_far_point_is_outside_geofence():
    inside, distance = is_inside_geofence(28.6139, 77.2090, 28.7041, 77.1025, 50)

    assert inside is False
    assert distance > 1000


def test_haversine_returns_reasonable_distance():
    distance = haversine_distance_meters(28.6139, 77.2090, 28.6141, 77.2092)

    assert 20 <= distance <= 40
