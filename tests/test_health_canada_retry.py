"""Tests for the Health Canada empty-response retry and the backup-run skip check."""

import io
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
os.environ.setdefault("BUCKET", "test-bucket")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-2")

from pipeline import health_canada as hc  # noqa: E402


def fake_urlopen(answers):
    """Return a urlopen stand-in that gives each JSON answer in turn."""
    calls = iter(answers)
    return lambda req, timeout=None: io.BytesIO(json.dumps(next(calls)).encode())


def test_empty_answers_are_retried_with_three_waits(monkeypatch):
    waits = []
    monkeypatch.setattr(hc.time, "sleep", waits.append)
    monkeypatch.setattr(hc.urllib.request, "urlopen", fake_urlopen([[], [], [], [{"protocol_id": 1}]]))
    assert hc.get_json("protocol") == [{"protocol_id": 1}]
    assert waits == [60, 180, 300]


def test_still_empty_after_all_waits_returns_empty(monkeypatch):
    monkeypatch.setattr(hc.time, "sleep", lambda s: None)
    monkeypatch.setattr(hc.urllib.request, "urlopen", fake_urlopen([[], [], [], []]))
    assert hc.get_json("protocol") == []


def test_backup_run_skips_when_today_is_saved(monkeypatch):
    from datetime import datetime, timezone
    from unittest import mock

    # boto3 is not installed on every dev machine; the handler needs only a stand-in client
    monkeypatch.setitem(sys.modules, "boto3", mock.MagicMock())
    from pipeline import health_canada_lambda as lam

    today = datetime.now(timezone.utc).date().isoformat()
    monkeypatch.setattr(lam, "get_text", lambda key: json.dumps({"snapshot_date": today}))
    monkeypatch.setattr(lam.hc, "get_json", lambda name: (_ for _ in ()).throw(AssertionError("downloaded")))
    assert lam.handler({}, None) == {"skipped": True, "snapshot_date": today}


def test_first_try_stops_quietly_and_backup_raises(monkeypatch):
    import pytest
    from unittest import mock

    monkeypatch.setitem(sys.modules, "boto3", mock.MagicMock())
    from pipeline import health_canada_lambda as lam

    monkeypatch.setattr(lam, "get_text", lambda key: None)
    monkeypatch.setattr(lam.hc, "get_json", lambda name: [])
    assert lam.handler({"first_try": True}, None) == {"api_down": True, "endpoint": "protocol"}
    with pytest.raises(ValueError):
        lam.handler({}, None)
