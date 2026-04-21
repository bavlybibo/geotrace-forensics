from app.core.gps_utils import dms_to_decimal, format_coordinates


def test_gps_conversion_north_east():
    latitude = dms_to_decimal([30, 2, 39.84], "N")
    longitude = dms_to_decimal([31, 14, 8.52], "E")
    assert round(latitude, 4) == 30.0444
    assert round(longitude, 4) == 31.2357
    assert format_coordinates(latitude, longitude).startswith("30.0444")
