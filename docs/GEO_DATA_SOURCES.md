# GeoTrace Offline Geo Data Sources & Scaling Plan

GeoTrace must keep **native GPS**, **derived map coordinates**, and **text-only location leads** separated. This document explains how to grow the offline country/city/POI index without turning weak matches into false GPS claims.

## What changed in v12.10.25

- Added `data/osint/geo_aliases.json` for Arabic/English country and city normalization.
- Expanded `data/osint/local_geocoder_places.json` from a small seed into a broader MENA + Europe + global landmark seed.
- Added `app/core/osint/geo_normalizer.py` for Arabic normalization, accent removal, alias enrichment, city/country canonicalization, and conservative fuzzy matching.
- Enhanced `app/core/osint/offline_geocoder.py` to load three layers:
  1. `generated_geocoder_index.json` if you create one from public exports.
  2. `local_geocoder_places.json` bundled with the app.
  3. Hardcoded fallback rows.
- Added `tools/build_offline_geocoder_index.py` so the project can import bigger datasets locally instead of shipping huge files in GitHub.

## Recommended public/open sources

### 1. GeoNames dump
Best for: global cities, alternate names, population, country codes.

Suggested files:
- `allCountries.zip` or smaller country files.
- `cities500.zip`, `cities1000.zip`, `cities5000.zip`, or `cities15000.zip`.
- `alternateNamesV2.zip` when you need language-specific Arabic/English aliases.

Recommended product use:
- Import only cities above a population threshold for the default package.
- Keep a larger optional generated index outside Git if it becomes too big.

### 2. Natural Earth Populated Places
Best for: curated city/capital seed data that is small, clean, and public-domain friendly.

Recommended product use:
- Use it as the default global city backbone.
- Combine with GeoNames aliases for better OCR matching.

### 3. OpenStreetMap / self-hosted Nominatim
Best for: rich geocoding and address search.

Recommended product use:
- Do **not** silently send case evidence to public Nominatim.
- Prefer self-hosted Nominatim for heavy usage.
- If online lookup is enabled, require explicit analyst approval and write the action to the audit log.

### 4. Wikidata export / SPARQL result CSV
Best for: POIs, landmarks, multilingual labels, and coordinates.

Recommended product use:
- Export a controlled CSV/JSON with item label, Arabic label, English label, aliases, coordinate location, and country/city hints.
- Import it into `generated_geocoder_index.json` as an optional enrichment layer.

## Import workflow

Place downloaded/extracted files in a local folder outside case evidence, then run:

```powershell
python tools\build_offline_geocoder_index.py C:\geo-data\cities15000.txt --min-population 50000
```

For a CSV exported from Natural Earth or Wikidata:

```powershell
python tools\build_offline_geocoder_index.py C:\geo-data\natural_earth_populated_places.csv
```

The tool writes:

```text
data/osint/generated_geocoder_index.json
```

For your processed GeoNames JSON file, use:

```powershell
python tools\build_offline_geocoder_index.py C:\Users\PC\data\geo\processed\places_geonames.json --output data\osint\generated_geocoder_index.json --min-population 50000
```

This accepts both formats:

```text
data/geo/processed/places_geonames.json   # source/build file
```

and writes the runtime index here:

```text
data/osint/generated_geocoder_index.json  # loaded automatically by GeoTrace
```

Keep only one formatted or minified copy of the same `places_geonames.json`; duplicated copies are not needed.


That file is loaded automatically by the offline geocoder when present.

## Analyst safety rules

- A local geocoder hit is **not GPS**.
- A map screenshot label is **not device location**.
- A short map URL or place name is **derived geo context** until validated.
- Native EXIF GPS remains the strongest coordinate source.
- Always include limitations in exported reports when the result came from OCR, aliases, map screenshots, or fuzzy matching.

## Suggested accuracy checks

Before calling the dataset production-grade, build a validation set with:

- Arabic OCR screenshots from Google Maps.
- English OCR screenshots from Google Maps / Apple Maps / OSM.
- Route screenshots with start/end labels.
- False-positive cases: images named `cairo.jpg` but containing no map/location evidence.
- Similar city names and misspellings: `Alxandria`, `Jiddah`, `القاهره`, `اسكندريه`.

Track:

- top-1 city accuracy,
- top-3 city accuracy,
- POI precision,
- false location rate,
- filename-only false positive rate,
- Arabic alias hit rate.


## v12.10.28 Optional Stack / Data Notes

- `data/geo/raw/cities15000.txt` and `data/geo/raw/cities15000.zip` are now first-class import inputs.
- `requirements-ui.txt`, `requirements-geo.txt`, `requirements-ai.txt`, and `requirements-osint.txt` separate safe dependencies from heavy AI dependencies.
- Online connectors are privacy-gated. They do not run unless `GEOTRACE_OSINT_ONLINE=1` or `GEOTRACE_ONLINE_MAP_LOOKUP=1` is set by the analyst.
- The H3 confidence-cell helper is optional and falls back to a local bounding-box polygon when `h3` is not installed.
