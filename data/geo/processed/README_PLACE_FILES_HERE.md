# Put processed Geo data here

Place your prepared GeoNames/Natural Earth/Wikidata export files in this folder.

Recommended file name for the JSON you generated:

```text
places_geonames.json
```

Then run from the project root:

```powershell
python tools\build_offline_geocoder_index.py
```

The generated runtime index will be written to:

```text
data/osint/generated_geocoder_index.json
```

GeoTrace treats matches from this database as **Derived Location Leads** only. They are not native GPS evidence.
