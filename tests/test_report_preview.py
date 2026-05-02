from app.core.report_preview import render_report_preview


def test_report_preview_empty_case_is_readable():
    text = render_report_preview([], privacy_level='redacted_text', export_mode='Shareable Redacted')
    assert 'Shareable Redacted' in text
    assert 'Privacy' in text or 'privacy' in text
