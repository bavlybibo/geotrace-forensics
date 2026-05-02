from app.core.gps_utils import dms_to_decimal, ratio_to_float
from app.core.map.provider_bridge import build_map_provider_bridge
from app.core.osint.map_url_parser import parse_first_coordinate, parse_map_url_signals


class _Ratio:
    def __init__(self, num, den):
        self.num = num
        self.den = den


def test_gps_ratio_and_dms_formats_are_normalized():
    assert ratio_to_float(_Ratio(3, 2)) == 1.5
    assert round(dms_to_decimal([(40, 1), (28, 1), (54048, 1000)], "N"), 6) == 40.48168


def test_map_url_parser_reads_osm_and_labelled_coordinates():
    signals = parse_map_url_signals([
        "https://www.openstreetmap.org/?mlat=40.48168&mlon=-3.21450#map=16/40.48168/-3.21450"
    ])
    assert signals
    assert signals[0].coordinates == (40.48168, -3.2145)
    assert parse_first_coordinate(["lat: 40.48168 lon: -3.21450"]) == (40.48168, -3.2145)


def test_provider_bridge_builds_privacy_gated_map_links():
    class Record:
        gps_latitude = 40.48168
        gps_longitude = -3.21450
        gps_display = "40.481680, -3.214500"
        derived_latitude = None
        derived_longitude = None
        map_interactive_payload = {}
        possible_place = ""
        location_estimate_label = ""
        candidate_area = ""
        candidate_city = ""
        landmarks_detected = []
        place_candidates = []

    bridge = build_map_provider_bridge(Record())
    assert bridge.status == "native_gps_bridge_ready"
    assert len(bridge.provider_links) >= 3
    assert {link.provider for link in bridge.provider_links} >= {"Google Maps", "OpenStreetMap", "Apple Maps"}
