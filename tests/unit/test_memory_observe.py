"""Unit tests for the SDD-069 M028 observation event stream
`scripts/intelligence/memory-observe.py` — auto-feed admission from the real OCSF span log.

Covers: the comprehensive span→trigger→type mapping (session_reap / cockpit_action ok+fail
/ decisions / save-state / gate / dashboard / generic error); the feedback-loop exclusion
(`^memory_` spans never re-observed); idempotency (a re-run admits nothing new — cursor +
admit's _is_duplicate); honest-defer (absent/empty span log → 0 admitted, never crashes);
DRY-RUN default (no --confirm → nothing minted, cursor not advanced); summaries built from
REAL attributes; and the cursor high-water-mark (same-ms spans not dropped).

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
OBS_PATH = REPO_ROOT / "scripts" / "intelligence" / "memory-observe.py"


def _load():
    spec = importlib.util.spec_from_file_location("memory_observe", OBS_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


O = _load()
S = O._store  # the shared memory-store module


@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "STORE", tmp_path / "store.json")
    monkeypatch.setattr(S, "CHANGES", tmp_path / "changes.json")
    monkeypatch.setattr(S, "SPAN_STORE", tmp_path / "spans.jsonl")
    monkeypatch.setattr(S, "MEMORY_STATE", tmp_path / "memory.json")
    monkeypatch.setattr(O, "CURSOR", tmp_path / "observe.cursor")
    monkeypatch.delenv("SOVEREIGN_OS_DRY_RUN", raising=False)
    return tmp_path


def _span(op, sid, ts, *, sev="info", **attrs):
    return {"operation": op, "span_id": sid, "start_ts": ts, "severity": sev,
            "attributes": attrs}


def _seed_spans(store_dir, spans):
    (store_dir / "spans.jsonl").write_text(
        "\n".join(json.dumps(s) for s in spans) + "\n")


def _entries():
    return list(S._entries().values())


def _by_summary_prefix(prefix):
    return [e for e in _entries() if str(e.get("summary", "")).startswith(prefix)]


# ── mapping ────────────────────────────────────────────────────────────────────

def test_maps_the_comprehensive_span_set(store):
    _seed_spans(store, [
        _span("session_reap", "s1", "2026-01-01T00:00:01+00:00",
              session_id="sess-x", reason="process-exited"),
        _span("cockpit_action", "s2", "2026-01-01T00:00:02+00:00", sev="error",
              control_id="foo", exit_code=3),
        _span("cockpit_action", "s3", "2026-01-01T00:00:03+00:00",
              control_id="bar", exit_code=0),
        _span("approval_decision", "s4", "2026-01-01T00:00:04+00:00", verb="approve"),
        _span("session_save_state", "s5", "2026-01-01T00:00:05+00:00", record="ck-1"),
        _span("adapter_gate_advance", "s6", "2026-01-01T00:00:06+00:00", gate="eval"),
        _span("dashboard_toggle", "s7", "2026-01-01T00:00:07+00:00",
              dashboard="d-07", enabled=True, rationale="ops"),
    ])
    r = O.run(confirm=True)
    assert r["mapped"] == 7 and r["admitted_count"] == 7
    types = sorted(e["type"] for e in _entries())
    # reap(2) fail(2) ok(4) decision(6) save(4) gate(4) toggle(6)
    assert types == [2, 2, 4, 4, 4, 6, 6]
    # trigger provenance recorded via admit's admitted_via
    triggers = {e.get("admitted_via") for e in _entries()}
    assert {"task-outcome", "model-mistake", "tool-worked", "preference",
            "high-value-reuse"} <= triggers


def test_cockpit_exit_code_splits_worked_vs_mistake(store):
    _seed_spans(store, [
        _span("cockpit_action", "s1", "2026-01-01T00:00:01+00:00", control_id="a", exit_code=0),
        _span("cockpit_action", "s2", "2026-01-01T00:00:02+00:00", sev="error",
              control_id="b", exit_code=1),
    ])
    O.run(confirm=True)
    ok = _by_summary_prefix("cockpit action ok")
    bad = _by_summary_prefix("cockpit action failed")
    assert len(ok) == 1 and ok[0]["type"] == 4 and ok[0]["admitted_via"] == "tool-worked"
    assert len(bad) == 1 and bad[0]["type"] == 2 and bad[0]["admitted_via"] == "model-mistake"


def test_summaries_use_real_attributes(store):
    _seed_spans(store, [_span("session_reap", "s1", "2026-01-01T00:00:01+00:00",
                              session_id="sess-9", reason="process-exited")])
    O.run(confirm=True)
    s = _entries()[0]["summary"]
    assert "sess-9" in s and "process-exited" in s   # real attribute values, not fabricated


def test_generic_error_span_maps_to_model_mistake(store):
    _seed_spans(store, [_span("perimeter_alert", "s1", "2026-01-01T00:00:01+00:00",
                              sev="critical", rule="R1")])
    O.run(confirm=True)
    assert _entries()[0]["type"] == 2 and _entries()[0]["admitted_via"] == "model-mistake"


def test_non_memory_worthy_span_skipped(store):
    # an info-severity span with no mapped operation contributes nothing.
    _seed_spans(store, [_span("healthz_poll", "s1", "2026-01-01T00:00:01+00:00")])
    r = O.run(confirm=True)
    assert r["mapped"] == 0 and r["skipped"] == 1 and _entries() == []


# ── feedback-loop exclusion ─────────────────────────────────────────────────────

def test_memory_spans_are_never_observed(store):
    _seed_spans(store, [
        _span("memory_admit", "s1", "2026-01-01T00:00:01+00:00", mem_id="mem-z", trigger="new-fact"),
        _span("memory_advance", "s2", "2026-01-01T00:00:02+00:00", mem_id="mem-z"),
        _span("memory_decision", "s3", "2026-01-01T00:00:03+00:00", verb="approve"),
    ])
    r = O.run(confirm=True)
    assert r["mapped"] == 0 and r["admitted_count"] == 0 and _entries() == []


def test_no_feedback_loop_across_runs(store):
    # a real event → admit → admit emits a memory_admit span into the SAME log; a
    # second run consumes it but must NOT re-admit (else an infinite loop).
    _seed_spans(store, [_span("session_reap", "s1", "2026-01-01T00:00:01+00:00",
                              session_id="sess-x", reason="process-exited")])
    r1 = O.run(confirm=True)
    assert r1["admitted_count"] == 1
    r2 = O.run(confirm=True)     # sees the memory_admit span r1 appended
    assert r2["admitted_count"] == 0    # excluded — no feedback loop
    assert len(_entries()) == 1          # still exactly one memory


# ── idempotency ─────────────────────────────────────────────────────────────────

def test_rerun_admits_nothing_new(store):
    _seed_spans(store, [
        _span("session_reap", "s1", "2026-01-01T00:00:01+00:00", session_id="a", reason="x"),
        _span("cockpit_action", "s2", "2026-01-01T00:00:02+00:00", control_id="c", exit_code=0),
    ])
    assert O.run(confirm=True)["admitted_count"] == 2
    assert O.run(confirm=True)["admitted_count"] == 0    # cursor + dedup
    assert len(_by_summary_prefix("session reaped")) == 1


def test_cursor_advances_and_persists(store):
    _seed_spans(store, [_span("session_reap", "s1", "2026-01-01T00:00:01+00:00",
                              session_id="a", reason="x")])
    O.run(confirm=True)
    st = O.status()
    assert st["cursor_ts"] is not None and st["would_admit"] == 0


def test_same_ms_spans_not_dropped(store):
    # two distinct spans at the EXACT same start_ts must both be observed.
    ts = "2026-01-01T00:00:01+00:00"
    _seed_spans(store, [
        _span("session_reap", "s1", ts, session_id="a", reason="x"),
        _span("session_save_state", "s2", ts, record="ck"),
    ])
    assert O.run(confirm=True)["admitted_count"] == 2


# ── DRY-RUN + honest-defer ──────────────────────────────────────────────────────

def test_dry_run_default_mints_nothing_and_keeps_cursor(store):
    _seed_spans(store, [_span("session_reap", "s1", "2026-01-01T00:00:01+00:00",
                              session_id="a", reason="x")])
    r = O.run()   # no --confirm
    assert r["dry_run"] is True and r["admitted_count"] == 0 and r["cursor_advanced"] is False
    assert _entries() == []
    assert not (store / "observe.cursor").exists()   # dry-run never consumes


def test_honest_defer_on_absent_span_log(store):
    # no spans.jsonl seeded at all.
    r = O.run(confirm=True)
    assert r["ok"] is True and r["observed"] == 0 and r["admitted_count"] == 0
    assert _entries() == []


def test_status_is_read_only(store):
    _seed_spans(store, [_span("session_reap", "s1", "2026-01-01T00:00:01+00:00",
                              session_id="a", reason="x")])
    st = O.status()
    assert st["pending_spans"] == 1 and st["would_admit"] == 1
    assert _entries() == [] and not (store / "observe.cursor").exists()  # status mutates nothing
