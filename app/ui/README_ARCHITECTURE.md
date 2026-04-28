# UI Architecture

## v12.10.2 organization

- `main_window.py` is now a compatibility facade.
- Main window implementation lives in `window/main_window.py`.
- CTF GeoLocator implementation lives in `pages/ctf/geolocator_page.py`.
- Existing page import paths remain valid.

## Next split candidates

- Header/command bar builder
- Dashboard builder
- Reports page builder
- Cases page builder
- Settings and shortcuts controller
