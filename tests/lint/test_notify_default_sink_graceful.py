"""The notify dispatch DEFAULT file sink degrades gracefully when unwritable.

The default `file` channel is the privileged `/var/log/sovereign-os/notify.jsonl`
path. On an unprivileged host / CI runner / sandbox it can't be created, and a
best-effort local audit trail must NOT hard-fail the whole dispatch (exit 1)
when a real notification channel may still have delivered — otherwise every
dispatch that runs without root, with the default config, spuriously "fails".

`deliver_file` therefore treats an OSError on the DEFAULT sink as a graceful
skip (ok=True, "skipped: … unavailable"), while an EXPLICITLY-configured sink
that fails stays a genuine delivery failure (ok=False → exit 1). This lint pins
that split so the graceful-skip can't silently regress into either a hard fail
(spurious CI red) or an over-broad swallow (a real configured sink's failure
hidden).

Regression: `tests/lint/test_compat_pre_change_gate.py::test_incompatible_state_flows_to_notifykit`
went red on CI (2026-07-21) because the default sink hit `[Errno 13] Permission
denied: '/var/log/sovereign-os'` on the runner.
"""
from __future__ import annotations

import importlib.util
import pathlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DISPATCH = REPO / "scripts" / "notify" / "dispatch.py"


def _load():
    spec = importlib.util.spec_from_file_location("_notify_dispatch", DISPATCH)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def _raise_permission(*_a, **_k):
    raise PermissionError(13, "Permission denied")


def test_default_sink_permission_error_is_skipped_not_failed(monkeypatch):
    d = _load()
    # force the sink's directory creation to fail with a permission error,
    # regardless of whether /var/log happens to be writable in this environment.
    monkeypatch.setattr(pathlib.Path, "mkdir", _raise_permission)
    events = [{"title": "compat", "priority": "high"}]

    ok, detail = d.deliver_file(
        {"path": str(d.DEFAULT_FILE_SINK)}, events, dry_run=False
    )
    assert ok is True, "an unavailable DEFAULT sink must not fail the dispatch"
    assert "skipped" in detail and "unavailable" in detail


def test_explicitly_configured_sink_failure_stays_fatal(monkeypatch):
    d = _load()
    monkeypatch.setattr(pathlib.Path, "mkdir", _raise_permission)
    events = [{"title": "compat", "priority": "high"}]

    ok, detail = d.deliver_file(
        {"path": "/nonexistent/explicit/sink/notify.jsonl"}, events, dry_run=False
    )
    assert ok is False, "an operator-configured sink that fails is a real failure"
    assert "file sink" in detail


def test_default_sink_still_writes_when_the_path_is_writable(tmp_path, monkeypatch):
    # point the default at a writable temp path; a normal write is unaffected.
    d = _load()
    sink = tmp_path / "notify.jsonl"
    monkeypatch.setattr(d, "DEFAULT_FILE_SINK", sink)
    events = [{"title": "compat", "priority": "high"}]
    ok, detail = d.deliver_file({"path": str(sink)}, events, dry_run=False)
    assert ok is True and "appended" in detail
    assert sink.read_text(encoding="utf-8").strip()
