from app.core.osint.geo_normalizer import normalize_country, normalize_city, fuzzy_ratio
from app.core.osint.offline_geocoder import match_offline_places, geocoder_data_sources


def test_geo_alias_normalization_ar_en():
    assert normalize_country('مصر') == 'Egypt'
    assert normalize_country('UAE') == 'United Arab Emirates'
    city, country = normalize_city('القاهره')
    assert city == 'Cairo'
    assert country == 'Egypt'


def test_offline_geocoder_arabic_and_fuzzy_hits():
    hits = match_offline_places(['خريطة من مدينة نصر إلى برج القاهره'])
    names = {hit['name'] for hit in hits}
    assert 'Cairo Tower' in names or 'Nasr City' in names
    assert all('native GPS' in ' '.join(hit['limitations']) for hit in hits)


def test_fuzzy_misspelling_and_sources_available():
    assert fuzzy_ratio('Alexandria', 'Alxandria') >= 0.88
    sources = geocoder_data_sources()
    assert any(row['name'] == 'GeoNames' for row in sources)
    assert any('Nominatim' in row['name'] or row['name'] == 'OpenStreetMap/Nominatim' for row in sources)
