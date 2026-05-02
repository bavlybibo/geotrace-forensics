# GeoTrace Project GeoData Import

GeoTrace does not download public datasets by itself. Put approved/open datasets
inside the project folder and run the local importer.

## Recommended layout

```text
data/
  geo/
    raw/
      cities1000.zip              # recommended wide GeoNames city coverage
      alternateNamesV2.zip        # recommended Arabic/English aliases
      countryInfo.txt             # optional ISO/country metadata
      admin1CodesASCII.txt        # optional state/governorate names
      admin2Codes.txt             # optional district/county names
      timeZones.txt               # optional timezone metadata
    processed/
      places_geonames.json        # optional pre-processed place JSON
```

## Best choice

If you already have `cities1000.zip`, keep it. It has wider coverage than
`cities15000.zip`. The extra file that matters most is:

```text
data/geo/raw/alternateNamesV2.zip
```

This improves Arabic/English aliases, OCR matching, and fuzzy city
normalization.

## Build the index

From the project root:

```bat
import_project_geo_data.bat
```

or:

```bat
python tools\build_offline_geocoder_index.py
```

Output:

```text
data/osint/generated_geocoder_index.json
```

## Supported primary files

- `cities1000.zip` / `.txt`
- `cities5000.zip` / `.txt`
- `cities15000.zip` / `.txt`
- `allCountries.zip` / `.txt`
- processed `.json`, `.geojson`, `.jsonl`, `.ndjson`, `.csv`, `.tsv`

## Supported helper files

- `alternateNamesV2.zip` / `.txt`
- `countryInfo.txt`
- `admin1CodesASCII.txt`
- `admin2Codes.txt`
- `timeZones.txt`

## Important evidence rule

Generated place matches are **derived location leads only**. Do not call them
native GPS. Corroborate with EXIF GPS, map URL, screenshot context, manual review,
or another independent source before final reporting.
