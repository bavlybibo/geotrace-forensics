from pathlib import Path
import sys

from app.core.vision.local_vision_model import detect_local_vision_model, run_optional_local_vision, self_test_local_vision


def test_local_vision_policy_blocks_shell_tokens(monkeypatch, tmp_path: Path):
    image = tmp_path / 'map.png'
    image.write_bytes(b'not-an-image-but-path-exists')
    monkeypatch.setenv('GEOTRACE_LOCAL_VISION_COMMAND', 'python tools/local_vision_runner_template.py && echo bad')
    status = detect_local_vision_model()
    assert status.policy_status == 'blocked'
    result = run_optional_local_vision(image)
    assert result.executed is False
    assert result.provider == 'local-vision-not-executed' or result.provider == 'local-vision-policy-blocked'


def test_local_vision_template_self_test_executes(monkeypatch):
    runner = Path(__file__).resolve().parents[1] / 'tools' / 'local_vision_runner_template.py'
    monkeypatch.setenv('GEOTRACE_LOCAL_VISION_COMMAND', f'{sys.executable} -S {runner}')
    payload = self_test_local_vision()
    assert payload['executed'] is True
    assert payload['provider'] == 'geotrace-local-vision-template'
    assert 'status' in payload
