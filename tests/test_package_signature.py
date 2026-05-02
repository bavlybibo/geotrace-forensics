import json
import hashlib

from app.core.reports.package_signature import write_package_signature, verify_package_signature


def test_package_signature_roundtrip(tmp_path):
    artifact = tmp_path / 'report.txt'
    artifact.write_text('hello', encoding='utf-8')
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    manifest = {
        'artifacts': {'report': {'relative_path': 'report.txt', 'file_name': 'report.txt', 'sha256': digest}},
        'report_assets': {},
    }
    (tmp_path / 'export_manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    write_package_signature(tmp_path)
    passed, message = verify_package_signature(tmp_path)
    assert passed, message
