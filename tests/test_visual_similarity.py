from pathlib import Path
import importlib.util

import pytest

pytestmark = pytest.mark.skipif(importlib.util.find_spec('PIL') is None, reason='Pillow is not installed')


def test_visual_similarity_search_finds_near_duplicate(tmp_path):
    from PIL import Image
    from tools.visual_similarity_search import search

    q = tmp_path / 'query.png'
    same = tmp_path / 'same.png'
    other = tmp_path / 'other.png'
    Image.new('RGB', (32, 32), (255, 255, 255)).save(q)
    Image.new('RGB', (32, 32), (255, 255, 255)).save(same)
    Image.new('RGB', (32, 32), (0, 0, 0)).save(other)

    result = search(q, tmp_path, threshold=90, limit=10)
    files = {Path(row['file']).name for row in result['matches']}
    assert 'same.png' in files
