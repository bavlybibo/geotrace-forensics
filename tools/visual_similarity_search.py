from __future__ import annotations

"""Local visual similarity search for GeoTrace evidence folders.

This tool never uploads images and never calls external services. It uses the
GeoTrace deterministic semantic fingerprint as a safe baseline. For true landmark
identity, connect a reviewed local CLIP/SigLIP runner separately and use this as
triage only.

Usage:
  python tools/visual_similarity_search.py query.jpg evidence_folder --threshold 82
  python tools/visual_similarity_search.py query.jpg evidence_folder --json
"""

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.vision.semantic_embeddings import build_semantic_image_profile, compare_semantic_profiles

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp', '.tif', '.tiff', '.heic', '.heif'}


def _iter_images(folder: Path) -> list[Path]:
    if folder.is_file() and folder.suffix.lower() in IMAGE_EXTENSIONS:
        return [folder]
    if not folder.exists():
        return []
    out: list[Path] = []
    for path in folder.rglob('*'):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            out.append(path)
    return sorted(out, key=lambda p: str(p).lower())


def search(query: Path, corpus: Path, threshold: float = 82.0, limit: int = 25) -> dict[str, Any]:
    q_profile = build_semantic_image_profile(query)
    rows: list[dict[str, Any]] = []
    for image in _iter_images(corpus):
        if image.resolve() == query.resolve():
            continue
        profile = build_semantic_image_profile(image)
        comparison = compare_semantic_profiles(q_profile, profile)
        score = float(comparison.get('score', 0) or 0)
        if score < threshold:
            continue
        rows.append({
            'file': str(image),
            'score': score,
            'label': comparison.get('label', 'unknown'),
            'shared_tags': comparison.get('shared_tags', []),
            'fingerprint': profile.fingerprint,
            'warnings': profile.warnings,
        })
    rows.sort(key=lambda row: (-float(row['score']), str(row['file']).lower()))
    return {
        'query': str(query),
        'query_fingerprint': q_profile.fingerprint,
        'threshold': threshold,
        'matches': rows[:limit],
        'match_count': len(rows),
        'note': 'Local deterministic similarity triage; verify manually before final reporting.',
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='GeoTrace local visual similarity search')
    parser.add_argument('query', type=Path)
    parser.add_argument('corpus', type=Path)
    parser.add_argument('--threshold', type=float, default=82.0)
    parser.add_argument('--limit', type=int, default=25)
    parser.add_argument('--json', action='store_true', dest='as_json')
    args = parser.parse_args(argv)

    if not args.query.exists():
        print(f'Query image not found: {args.query}', file=sys.stderr)
        return 2
    result = search(args.query, args.corpus, args.threshold, args.limit)
    if args.as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    print('GEOTRACE VISUAL SIMILARITY SEARCH')
    print('=' * 78)
    print(f"Query: {result['query']}")
    print(f"Fingerprint: {result['query_fingerprint']}")
    print(f"Threshold: {result['threshold']}")
    print(f"Matches: {result['match_count']}")
    print('')
    for row in result['matches']:
        print(f"{row['score']:6.2f}%  {row['label']:<24}  {row['file']}")
        if row.get('shared_tags'):
            print('        shared tags: ' + ', '.join(row['shared_tags']))
    if not result['matches']:
        print('No matches at this threshold.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
