# Demo Case Guide

For the strongest live demo, import these files together from `demo_evidence/`:

1. `cairo_scene.jpg` — native EXIF + native GPS
2. `giza_scene.jpg` — second geo anchor for map/timeline correlation
3. `edited_scene.jpg` — edited/exported workflow comparison
4. `no_exif.png` — metadata-thin asset
5. `no_exif_duplicate.png` — duplicate/near-duplicate review
6. `IMG_20260413_170405_hidden_payload.png` — hidden-content review candidate
7. `broken_animation.gif` — parser / fallback review candidate

Suggested live flow:
- Import the full set
- Open Review on a GPS-bearing item
- Show Timeline and Map
- Open Hidden / Code on the payload candidate
- Export HTML/PDF package from Reports
