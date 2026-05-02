from pathlib import Path

from PIL import Image

from app.core.map.intelligence import _good_place_candidate, analyze_map_intelligence


def test_generic_metadata_words_are_not_place_candidates():
    for value in ['exif', 'no exif', 'metadata', 'image', 'screenshot']:
        assert not _good_place_candidate(value)


def test_plain_no_exif_image_does_not_become_map(tmp_path: Path):
    path = tmp_path / 'no_exif.png'
    Image.new('RGB', (400, 260), 'white').save(path)
    result = analyze_map_intelligence(path, {
        'lines': ['No EXIF metadata available'],
        'ocr_map_labels': ['exif'],
        'visible_location_strings': [],
        'visible_urls': [],
        'raw_text': 'No EXIF metadata available',
        'excerpt': 'No EXIF metadata available',
        'app_names': [],
        'ocr_confidence': 50,
    })
    assert result.detected is False
    assert result.place_candidates == []
    assert result.confidence <= 20
