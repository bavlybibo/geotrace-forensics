import json
import subprocess
import sys
from pathlib import Path


def test_processed_geonames_json_import(tmp_path):
    root = Path(__file__).resolve().parents[1]
    sample = tmp_path / "places_geonames.json"
    sample.write_text(json.dumps([
        {
            "id": "geonames_360630",
            "source": "GeoNames",
            "name": "Cairo",
            "name_ascii": "Cairo",
            "aliases": ["Al Qahirah", "القاهرة", "القاهره"],
            "country_code": "EG",
            "lat": 30.0444,
            "lon": 31.2357,
            "feature_class": "P",
            "feature_code": "PPLC",
            "population": 9600000,
            "timezone": "Africa/Cairo",
            "importance": 1.0,
        }
    ], ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "generated_geocoder_index.json"
    subprocess.run([
        sys.executable,
        str(root / "tools" / "build_offline_geocoder_index.py"),
        str(sample),
        "--output",
        str(out),
        "--min-population",
        "0",
    ], cwd=root, check=True)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["places"][0]["name"] == "Cairo"
    assert data["places"][0]["country"] == "Egypt"
    assert "القاهرة" in data["places"][0]["aliases"]
