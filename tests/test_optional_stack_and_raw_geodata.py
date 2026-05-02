from pathlib import Path
import zipfile

from app.core.osint.geocell import build_geo_confidence_zone
from app.core.osint.geo_normalizer import fuzzy_ratio
from tools import build_offline_geocoder_index as importer


def test_requirement_groups_exist():
    root = Path(__file__).resolve().parents[1]
    for name in [
        "requirements-ui.txt",
        "requirements-geo.txt",
        "requirements-ai.txt",
        "requirements-osint.txt",
        "requirements-all.txt",
        "setup_full_stack_windows.bat",
        "tools/check_optional_stack.py",
    ]:
        assert (root / name).exists(), name


def test_raw_geonames_zip_loader(tmp_path):
    sample = (
        "3530597\tCairo\tCairo\tالقاهرة,Al Qahirah\t30.0444\t31.2357\tP\tPPLC\tEG\t\t11\t\t\t\t9606916\t\t23\tAfrica/Cairo\t2026-01-01\n"
    )
    archive = tmp_path / "cities15000.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("cities15000.txt", sample)
    rows = list(importer.load_geonames_zip(archive, source="geonames_zip", min_population=0, limit=10))
    assert rows and rows[0]["name"] == "Cairo"
    assert rows[0]["country"] == "Egypt"


def test_geocell_fallback_or_h3_available():
    zone = build_geo_confidence_zone(30.0444, 31.2357, radius_m=750, source="test")
    assert zone.available is True
    assert zone.geojson and zone.geojson["type"] == "Polygon"


def test_rapidfuzz_fallback_ratio_still_works():
    assert fuzzy_ratio("Alexandria", "Alxandria") >= 0.80


def test_geonames_auxiliary_enrichment(tmp_path):
    sample = (
        "3530597\tCairo\tCairo\tAl Qahirah\t30.0444\t31.2357\tP\tPPLC\tEG\t\t11\t\t\t\t9606916\t\t23\tAfrica/Cairo\t2026-01-01\n"
    )
    archive = tmp_path / "cities1000.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("cities1000.txt", sample)
    alt = tmp_path / "alternateNamesV2.zip"
    with zipfile.ZipFile(alt, "w") as zf:
        zf.writestr("alternateNamesV2.txt", "1\t3530597\tar\tالقاهرة\t1\t0\t0\t0\t\t\n")
    rows = list(importer.load_geonames_zip(archive, source="geonames_zip", min_population=0, limit=10))
    aux = importer._find_auxiliary_files(tmp_path, tmp_path, [archive])
    rows, stats = importer._enrich_rows_with_auxiliary(rows, aux)
    assert "القاهرة" in rows[0]["aliases"]
    assert stats["alternate_aliases_added"] >= 1
