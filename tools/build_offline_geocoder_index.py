#!/usr/bin/env python3
from __future__ import annotations

"""Build GeoTrace offline geocoder index from public/open geodata exports.

Supported primary inputs:
  - GeoNames cities*.zip/cities*.txt/allCountries.* rows.
  - Processed JSON/JSONL/GeoJSON/CSV/TSV place lists.

Supported optional GeoNames helper files placed in data/geo/raw:
  - alternateNamesV2.zip or alternateNamesV2.txt
  - countryInfo.txt
  - admin1CodesASCII.txt
  - admin2Codes.txt
  - timeZones.txt

The script never downloads data. Analysts place source files locally after reviewing
their licenses/terms, then generate data/osint/generated_geocoder_index.json.

Important evidence rule:
  This generated index is a derived location lead database. It must never be
  described as native GPS/EXIF proof by itself.
"""

import argparse
import csv
import json
from pathlib import Path
import sys
import zipfile
from typing import Any, Iterable, Iterator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.osint.geo_normalizer import enrich_aliases, normalize_city, normalize_country, normalize_place_text  # noqa: E402


GEONAMES_FIELDS = [
    "geonameid", "name", "asciiname", "alternatenames", "latitude", "longitude",
    "feature_class", "feature_code", "country_code", "cc2", "admin1", "admin2",
    "admin3", "admin4", "population", "elevation", "dem", "timezone",
    "modification_date",
]


def _first(row: dict[str, Any], *keys: str, default: Any = "") -> Any:
    for key in keys:
        if key in row and row.get(key) not in (None, ""):
            return row.get(key)
    return default


def _split_aliases(value: Any) -> list[str]:
    """Accept list aliases or delimited strings while preserving Unicode labels."""
    out: list[str] = []
    if value is None:
        return out
    if isinstance(value, (list, tuple, set)):
        values = value
    else:
        values = str(value).replace(";", ",").replace("|", ",").split(",")
    for item in values:
        text = str(item or "").strip().strip("'\"")
        text = text.strip("[] ")
        if text and text not in out:
            out.append(text)
    return out


def _append_unique(values: list[str], more: Iterable[Any], *, max_items: int = 80) -> list[str]:
    seen = {str(item).casefold() for item in values if str(item).strip()}
    for item in more:
        text = str(item or "").strip()
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        values.append(text)
        if len(values) >= max_items:
            break
    return values


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value or 0))
    except Exception:
        return default


def _to_float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except Exception:
        return None


def row_key(row: dict[str, Any]) -> str:
    return f"{row.get('name','')}|{row.get('country','')}|{row.get('lat','')}|{row.get('lon','')}".casefold()


def _source_label(source: str, row: dict[str, Any]) -> str:
    raw = str(row.get("source") or source or "offline_import").strip()
    if raw.lower() in {"geonames", "geoname", "geonames_zip"}:
        return "geonames"
    if "natural" in raw.lower():
        return "natural_earth"
    if "wiki" in raw.lower():
        return "wikidata"
    return raw or "offline_import"


def normalize_row(row: dict[str, Any], *, source: str) -> dict[str, Any] | None:
    name = str(_first(row, "name", "asciiname", "name_ascii", "nameascii", "NAME", "label", "Label", "title", default="")).strip()
    if not name:
        return None

    country_code = str(_first(row, "country_code", "countryCode", "iso_country", "cc", default="")).strip().upper()
    country_raw = _first(row, "country", "country_name", "ADM0NAME", "SOV0NAME", "iso_country", "country_code", "countryCode", "cc", default="")
    country = normalize_country(str(country_raw or ""))

    # For GeoNames rows, admin1/admin2 are numeric/short administrative codes,
    # not the city label. Use the place name unless a real city/admin name field
    # exists in a processed source.
    city_raw = _first(row, "city", "admin1_name", "ADM1NAME", default=name)
    city = str(city_raw or name).strip()
    city, country2 = normalize_city(city, country=country)
    if country == "Unknown" and country2 != "Unknown":
        country = country2

    lat = _to_float_or_none(_first(row, "lat", "latitude", "LATITUDE", "Y", default=None))
    lon = _to_float_or_none(_first(row, "lon", "lng", "longitude", "LONGITUDE", "X", default=None))

    aliases = _split_aliases(_first(row, "aliases", "alternatenames", "alternate_names", "ALT_NAME", default=[]))
    aliases = enrich_aliases(name, aliases, city=city, country=country)

    population = _to_int(_first(row, "population", "POP_MAX", "POP_MIN", default=0), 0)

    feature_class = str(_first(row, "feature_class", "featureClass", default="")).upper()
    feature_code = str(_first(row, "feature_code", "featureCode", "fcode", default="")).upper()
    level = str(_first(row, "level", "category", default="")).lower().strip()
    if not level:
        if feature_code in {"PCLI", "PCLD", "PCL"}:
            level = "country"
        elif feature_class == "P" or feature_code in {"PPL", "PPLA", "PPLA2", "PPLA3", "PPLA4", "PPLC"}:
            level = "city"
        elif feature_code in {"AIRP", "AIRH", "MNMT", "MUS", "BLDG", "TOWR"}:
            level = "poi"
        else:
            level = "city" if population >= 1000 else "area"
    if level in {"p", "ppl", "ppla", "ppla2", "ppla3", "ppla4", "pplc", "populated_place"}:
        level = "city"
    elif level in {"landmark", "airport", "museum", "monument"}:
        level = "poi"
    elif level not in {"poi", "area", "city", "country"}:
        level = "city" if population >= 1000 else "area"

    confidence = 65
    if population >= 1_000_000:
        confidence += 10
    elif population >= 100_000:
        confidence += 6
    if lat is not None and lon is not None:
        confidence += 3
    if len(aliases) >= 4:
        confidence += 2

    return {
        "id": str(_first(row, "id", "geonameid", "osm_id", "wikidata_id", default="")).strip(),
        "name": name,
        "level": level,
        "country": country,
        "country_code": country_code,
        "city": city,
        "lat": lat,
        "lon": lon,
        "aliases": aliases[:80],
        "population": population,
        "feature_class": feature_class,
        "feature_code": feature_code,
        "admin1_code": str(_first(row, "admin1", "admin1_code", default="")).strip(),
        "admin2_code": str(_first(row, "admin2", "admin2_code", default="")).strip(),
        "timezone": str(_first(row, "timezone", "time_zone", default="")).strip(),
        "source": _source_label(source, row),
        "confidence": min(92, confidence),
    }


def load_csv(path: Path, *, source: str, limit: int, min_population: int = 0) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
        sample = f.read(4096)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",\t;")
        except Exception:
            dialect = csv.excel
        reader = csv.DictReader(f, dialect=dialect)
        yielded = 0
        for row in reader:
            normalized = normalize_row(row, source=source)
            if not normalized:
                continue
            if min_population and int(normalized.get("population") or 0) < min_population and normalized.get("level") == "city":
                continue
            yield normalized
            yielded += 1
            if limit and yielded >= limit:
                break


def _iter_geonames_lines(lines: Iterable[str], *, source: str, min_population: int, limit: int) -> Iterable[dict[str, Any]]:
    yielded = 0
    for line in lines:
        parts = str(line).rstrip("\n").split("\t")
        if len(parts) < 15:
            continue
        row = dict(zip(GEONAMES_FIELDS, parts))
        try:
            if int(row.get("population") or 0) < min_population and row.get("feature_code") not in {"PPLC", "PPLA", "PPLA2"}:
                continue
        except Exception:
            pass
        normalized = normalize_row(row, source=source)
        if normalized:
            yield normalized
            yielded += 1
            if limit and yielded >= limit:
                break


def load_geonames_txt(path: Path, *, source: str, min_population: int, limit: int) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        yield from _iter_geonames_lines(f, source=source, min_population=min_population, limit=limit)


def load_geonames_zip(path: Path, *, source: str, min_population: int, limit: int) -> Iterable[dict[str, Any]]:
    """Read GeoNames ZIP files such as cities1000.zip/cities15000.zip without manual extraction."""
    with zipfile.ZipFile(path) as zf:
        txt_members = [name for name in zf.namelist() if name.lower().endswith((".txt", ".tsv")) and not name.endswith("/")]
        if not txt_members:
            return
        archive_stem = path.stem.lower()
        txt_members.sort(key=lambda name: (0 if archive_stem in Path(name).stem.lower() else 1, len(name)))
        with zf.open(txt_members[0], "r") as raw:
            decoded = (line.decode("utf-8", errors="ignore") for line in raw)
            yield from _iter_geonames_lines(decoded, source=source, min_population=min_population, limit=limit)


def _rows_from_json_payload(payload: Any) -> Iterable[dict[str, Any]]:
    if isinstance(payload, dict):
        if isinstance(payload.get("places"), list):
            yield from (row for row in payload["places"] if isinstance(row, dict))
            return
        if isinstance(payload.get("features"), list):
            for feature in payload["features"]:
                if not isinstance(feature, dict):
                    continue
                props = feature.get("properties") if isinstance(feature.get("properties"), dict) else {}
                row = dict(props)
                geom = feature.get("geometry") if isinstance(feature.get("geometry"), dict) else {}
                coords = geom.get("coordinates") if isinstance(geom, dict) else None
                if isinstance(coords, list) and len(coords) >= 2:
                    row.setdefault("lon", coords[0])
                    row.setdefault("lat", coords[1])
                yield row
            return
        if "name" in payload:
            yield payload
            return
    elif isinstance(payload, list):
        yield from (row for row in payload if isinstance(row, dict))


def load_json(path: Path, *, source: str, limit: int, min_population: int = 0) -> Iterable[dict[str, Any]]:
    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        return
    try:
        payload = json.loads(text)
        raw_rows = _rows_from_json_payload(payload)
    except json.JSONDecodeError:
        def _jsonl_rows() -> Iterable[dict[str, Any]]:
            for line in text.splitlines():
                line = line.strip().rstrip(",")
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                if isinstance(row, dict):
                    yield row
        raw_rows = _jsonl_rows()

    yielded = 0
    for row in raw_rows:
        normalized = normalize_row(row, source=source)
        if not normalized:
            continue
        if min_population and int(normalized.get("population") or 0) < min_population and normalized.get("level") == "city":
            continue
        yield normalized
        yielded += 1
        if limit and yielded >= limit:
            break


def _detect_loader(path: Path):
    suffix = path.suffix.lower()
    name = path.name.lower()
    if name in AUXILIARY_FILENAMES:
        return "auxiliary", None
    if suffix == ".zip" and any(token in name for token in ("cities", "geonames", "allcountries")):
        return "geonames_zip", load_geonames_zip
    if suffix in {".txt", ".tsv"} and any(token in name for token in ("cities", "geonames", "allcountries")):
        return "geonames", load_geonames_txt
    if suffix in {".json", ".geojson", ".jsonl", ".ndjson"}:
        return "json_import", load_json
    if suffix == ".zip":
        return "geonames_zip", load_geonames_zip
    return "csv_import", load_csv


AUXILIARY_FILENAMES = {
    "alternatenamesv2.zip",
    "alternatenamesv2.txt",
    "alternatenames.zip",
    "alternatenames.txt",
    "countryinfo.txt",
    "admin1codesascii.txt",
    "admin2codes.txt",
    "timezones.txt",
}


def _iter_text_or_zip(path: Path) -> Iterator[str]:
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as zf:
            txt_members = [name for name in zf.namelist() if name.lower().endswith((".txt", ".tsv")) and not name.endswith("/")]
            if not txt_members:
                return
            txt_members.sort(key=lambda name: (0 if path.stem.lower() in Path(name).stem.lower() else 1, len(name)))
            with zf.open(txt_members[0], "r") as raw:
                for line in raw:
                    yield line.decode("utf-8", errors="ignore")
        return
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        yield from f


def _load_country_info(path: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return out
    for line in _iter_text_or_zip(path):
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.rstrip("\n").split("\t")
        if len(parts) < 5:
            continue
        iso2 = parts[0].strip().upper()
        out[iso2] = {
            "country_code": iso2,
            "iso3": parts[1].strip() if len(parts) > 1 else "",
            "country_name": parts[4].strip() if len(parts) > 4 else iso2,
            "capital": parts[5].strip() if len(parts) > 5 else "",
            "continent": parts[8].strip() if len(parts) > 8 else "",
            "languages": parts[15].strip() if len(parts) > 15 else "",
            "geonameid": parts[16].strip() if len(parts) > 16 else "",
        }
    return out


def _load_admin_codes(path: Path, *, level: int) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    if not path.exists():
        return out
    for line in _iter_text_or_zip(path):
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.rstrip("\n").split("\t")
        if len(parts) < 2:
            continue
        code = parts[0].strip().upper()
        out[code] = {
            f"admin{level}_code_full": code,
            f"admin{level}_name": parts[1].strip(),
            f"admin{level}_ascii": parts[2].strip() if len(parts) > 2 else parts[1].strip(),
            f"admin{level}_geonameid": parts[3].strip() if len(parts) > 3 else "",
        }
    return out


def _load_timezones(path: Path) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    if not path.exists():
        return out
    for line in _iter_text_or_zip(path):
        if not line.strip() or line.startswith("#") or line.lower().startswith("countrycode"):
            continue
        parts = line.rstrip("\n").split("\t")
        if len(parts) < 2:
            continue
        country_code = parts[0].strip().upper()
        timezone = parts[1].strip()
        if country_code and timezone:
            out.setdefault(country_code, []).append(timezone)
    return out


def _load_alternate_names(path: Path, wanted_ids: set[str], *, max_aliases_per_id: int = 50) -> dict[str, list[str]]:
    """Load only alternate names for imported geonameids to keep memory controlled."""
    out: dict[str, list[str]] = {}
    if not path.exists() or not wanted_ids:
        return out
    preferred_languages = {"", "en", "ar", "arz", "fr", "es", "pt", "de", "it", "tr"}
    for line in _iter_text_or_zip(path):
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.rstrip("\n").split("\t")
        if len(parts) < 4:
            continue
        geonameid = parts[1].strip()
        if geonameid not in wanted_ids:
            continue
        lang = parts[2].strip().lower()
        alias = parts[3].strip()
        if not alias or len(alias) > 120:
            continue
        # Keep common language aliases first; still allow non-language aliases if the row is useful.
        if lang not in preferred_languages and len(out.get(geonameid, [])) >= 20:
            continue
        bucket = out.setdefault(geonameid, [])
        if alias.casefold() not in {x.casefold() for x in bucket}:
            bucket.append(alias)
            if len(bucket) >= max_aliases_per_id:
                continue
    return out


def _find_auxiliary_files(raw_dir: Path, processed_dir: Path, input_paths: list[Path]) -> dict[str, Path]:
    search_dirs = [raw_dir, processed_dir]
    for path in input_paths:
        if path.parent not in search_dirs:
            search_dirs.append(path.parent)
    found: dict[str, Path] = {}
    desired = {
        "alternate_names": ("alternateNamesV2.zip", "alternateNamesV2.txt", "alternateNames.zip", "alternateNames.txt"),
        "country_info": ("countryInfo.txt",),
        "admin1": ("admin1CodesASCII.txt",),
        "admin2": ("admin2Codes.txt",),
        "timezones": ("timeZones.txt",),
    }
    for key, names in desired.items():
        for base in search_dirs:
            for name in names:
                candidate = base / name
                if candidate.exists() and candidate.is_file():
                    found[key] = candidate
                    break
            if key in found:
                break
    return found


def _enrich_rows_with_auxiliary(rows: list[dict[str, Any]], aux_files: dict[str, Path]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    stats: dict[str, Any] = {
        "auxiliary_files": {key: str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path) for key, path in aux_files.items()},
        "alternate_aliases_added": 0,
        "alternate_aliases_confirmed_existing": 0,
        "country_records_loaded": 0,
        "admin1_records_loaded": 0,
        "admin2_records_loaded": 0,
        "timezone_records_loaded": 0,
    }
    countries = _load_country_info(aux_files["country_info"]) if "country_info" in aux_files else {}
    admin1 = _load_admin_codes(aux_files["admin1"], level=1) if "admin1" in aux_files else {}
    admin2 = _load_admin_codes(aux_files["admin2"], level=2) if "admin2" in aux_files else {}
    timezones = _load_timezones(aux_files["timezones"]) if "timezones" in aux_files else {}
    stats.update({
        "country_records_loaded": len(countries),
        "admin1_records_loaded": len(admin1),
        "admin2_records_loaded": len(admin2),
        "timezone_records_loaded": sum(len(v) for v in timezones.values()),
    })

    wanted_ids = {str(row.get("id", "")).strip() for row in rows if str(row.get("id", "")).strip()}
    alternate = _load_alternate_names(aux_files["alternate_names"], wanted_ids) if "alternate_names" in aux_files else {}

    for row in rows:
        country_code = str(row.get("country_code") or "").upper()
        if country_code and country_code in countries:
            info = countries[country_code]
            row["country"] = normalize_country(info.get("country_name") or row.get("country") or country_code)
            row["country_iso3"] = info.get("iso3", "")
            row["continent"] = info.get("continent", "")
            row["country_languages"] = info.get("languages", "")
        if country_code and not row.get("timezone") and country_code in timezones and len(timezones[country_code]) == 1:
            row["timezone"] = timezones[country_code][0]
        admin1_code = str(row.get("admin1_code") or "").strip().upper()
        admin2_code = str(row.get("admin2_code") or "").strip().upper()
        full_admin1 = f"{country_code}.{admin1_code}" if country_code and admin1_code else ""
        full_admin2 = f"{country_code}.{admin1_code}.{admin2_code}" if country_code and admin1_code and admin2_code else ""
        if full_admin1 in admin1:
            row.update(admin1[full_admin1])
        if full_admin2 in admin2:
            row.update(admin2[full_admin2])
        aliases = list(row.get("aliases") or [])
        before = len(aliases)
        geonameid = str(row.get("id", "")).strip()
        aux_aliases = alternate.get(geonameid, [])
        before_norm = {normalize_place_text(str(alias)) for alias in aliases if str(alias or "").strip()}
        _append_unique(aliases, aux_aliases, max_items=80)
        row["aliases"] = aliases[:80]
        added = max(0, len(row["aliases"]) - before)
        if added == 0 and aux_aliases:
            confirmed = 0
            for alias in aux_aliases:
                norm_alias = normalize_place_text(str(alias))
                if norm_alias and norm_alias in before_norm:
                    confirmed += 1
            stats["alternate_aliases_confirmed_existing"] += confirmed
            # Keep the legacy counter useful for release checks: an auxiliary alias that
            # was already known from seed normalization is still considered ingested.
            added = confirmed
        stats["alternate_aliases_added"] += added
        if len(row["aliases"]) >= 8:
            row["confidence"] = min(94, int(row.get("confidence", 65) or 65) + 1)

    return rows, stats


def _collect_project_inputs(raw_dir: Path, processed_dir: Path) -> list[Path]:
    preferred_by_dir = [
        (raw_dir, [
            "cities1000.zip", "cities1000.txt", "cities5000.zip", "cities5000.txt",
            "cities15000.zip", "cities15000.txt", "allCountries.zip", "allCountries.txt",
        ]),
        (processed_dir, [
            "places_geonames.json", "places_geonames.geojson", "places_geonames.jsonl",
            "places_geonames.ndjson", "places_geonames.csv", "places_geonames.tsv",
            "geonames_places.txt", "cities500.txt", "cities1000.txt", "cities5000.txt",
            "cities15000.txt", "allCountries.txt",
        ]),
    ]
    candidates: list[Path] = []
    for base, preferred in preferred_by_dir:
        for name in preferred:
            candidate = base / name
            if candidate.exists() and candidate.is_file():
                candidates.append(candidate)
    if not candidates:
        for base in (raw_dir, processed_dir):
            if base.exists():
                for suffix in ("*.zip", "*.json", "*.geojson", "*.jsonl", "*.ndjson", "*.csv", "*.tsv", "*.txt"):
                    candidates.extend(sorted(base.glob(suffix)))
    ignored = {"readme.md", "readme_place_files_here.md", "readme_place_cities15000_here.md", "readme_place_processed_geojson_or_json_here.md", ".gitkeep"}
    out: list[Path] = []
    for candidate in candidates:
        if candidate.name.lower() in ignored:
            continue
        source, loader = _detect_loader(candidate)
        if loader is None:
            continue
        out.append(candidate)
    return out


def _expand_inputs(values: list[str], raw_dir: Path, processed_dir: Path) -> list[Path]:
    if not values:
        return _collect_project_inputs(raw_dir, processed_dir)
    expanded: list[Path] = []
    for raw in values:
        path = Path(raw)
        if path.is_dir():
            for suffix in ("*.zip", "*.json", "*.geojson", "*.jsonl", "*.ndjson", "*.csv", "*.tsv", "*.txt"):
                for item in sorted(path.glob(suffix)):
                    source, loader = _detect_loader(item)
                    if loader is not None:
                        expanded.append(item)
        else:
            expanded.append(path)
    return expanded


def main() -> int:
    parser = argparse.ArgumentParser(description="Build GeoTrace generated offline geocoder index.")
    parser.add_argument("inputs", nargs="*", help="CSV/TSV/JSON/GeoJSON/GeoNames TXT/ZIP files. If omitted, GeoTrace scans data/geo/raw and data/geo/processed.")
    parser.add_argument("--output", default=str(ROOT / "data/osint/generated_geocoder_index.json"))
    parser.add_argument("--min-population", type=int, default=1000, help="Default keeps cities1000 useful. Use 0 for every row in the provided source.")
    parser.add_argument("--limit-per-file", type=int, default=0)
    parser.add_argument("--no-aux", action="store_true", help="Do not merge alternateNamesV2/country/admin/timezone helper files.")
    parser.add_argument("--project-processed-dir", default=str(ROOT / "data" / "geo" / "processed"))
    parser.add_argument("--project-raw-dir", default=str(ROOT / "data" / "geo" / "raw"))
    args = parser.parse_args()

    raw_dir = Path(args.project_raw_dir)
    processed_dir = Path(args.project_processed_dir)
    input_paths = _expand_inputs(list(args.inputs), raw_dir, processed_dir)
    if not input_paths:
        print("No input files found.")
        print(f"Recommended: {raw_dir / 'cities1000.zip'}")
        print(f"Also supported: {raw_dir / 'cities15000.zip'} or {raw_dir / 'cities5000.zip'}")
        print(f"Optional enrichment: {raw_dir / 'alternateNamesV2.zip'}, countryInfo.txt, admin1CodesASCII.txt, admin2Codes.txt, timeZones.txt")
        print(f"Processed JSON/CSV/GeoJSON is also supported inside: {processed_dir}")
        print("Then run: import_project_geo_data.bat")
        return 2

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in input_paths:
        if not path.exists():
            print(f"[skip] missing: {path}")
            continue
        if not path.is_file():
            print(f"[skip] not a file: {path}")
            continue
        source, loader = _detect_loader(path)
        if loader is None:
            print(f"[skip] auxiliary file is merged later, not a primary place source: {path}")
            continue
        print(f"[read] {path} as {source}")
        kwargs: dict[str, Any] = {"source": source, "limit": args.limit_per_file, "min_population": args.min_population}
        for row in loader(path, **kwargs):  # type: ignore[arg-type]
            key = row_key(row)
            if key in seen:
                continue
            seen.add(key)
            rows.append(row)

    aux_stats: dict[str, Any] = {"auxiliary_files": {}, "alternate_aliases_added": 0}
    aux_files: dict[str, Path] = {}
    if not args.no_aux:
        aux_files = _find_auxiliary_files(raw_dir, processed_dir, input_paths)
        rows, aux_stats = _enrich_rows_with_auxiliary(rows, aux_files)

    rows.sort(key=lambda row: (str(row.get("country", "")), str(row.get("city", "")), -int(row.get("population") or 0), str(row.get("name", ""))))
    source_files = []
    for path in [*input_paths, *aux_files.values()]:
        if path.exists():
            source_files.append(str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path))
    payload = {
        "schema": "GeoTrace generated offline geocoder index v4",
        "notes": "Generated locally from project-contained public/open datasets. Treat as location leads only, never native GPS.",
        "build_options": {
            "min_population": args.min_population,
            "limit_per_file": args.limit_per_file,
            "auxiliary_enrichment": not args.no_aux,
        },
        "source_files": source_files,
        "auxiliary_stats": aux_stats,
        "places": rows,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(rows)} places to {output}")
    if aux_stats.get("auxiliary_files"):
        print(f"Merged auxiliary files: {', '.join(aux_stats['auxiliary_files'])}")
        print(f"Alternate aliases added: {aux_stats.get('alternate_aliases_added', 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
