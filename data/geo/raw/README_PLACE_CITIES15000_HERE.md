# Place GeoNames raw files here

Recommended global offline city database:

```text
data/geo/raw/cities1000.zip
```

Also supported:

```text
data/geo/raw/cities5000.zip
data/geo/raw/cities15000.zip
data/geo/raw/allCountries.zip
```

Recommended enrichment files:

```text
data/geo/raw/alternateNamesV2.zip
data/geo/raw/countryInfo.txt
data/geo/raw/admin1CodesASCII.txt
data/geo/raw/admin2Codes.txt
data/geo/raw/timeZones.txt
```

Then run from the project root:

```powershell
.\import_project_geo_data.bat
```

The importer creates:

```text
data/osint/generated_geocoder_index.json
```

Keep raw files local. GeoTrace treats this output as derived OSINT/location
leads, not native GPS evidence.
