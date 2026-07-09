"""Unit tests for the SDD-066 M028 SLM memory janitor
`scripts/intelligence/memory-janitor.py` (M00473 — the 7 cheap maintenance jobs).

Covers: the deterministic jobs (dedup marks later duplicates + keeps the earliest +
`dedup_of`, idempotent, never hard-deletes; graph-edges links topic/token-overlap
entries bidirectionally, idempotent; tag adds deterministic token tags, idempotent);
the SLM-routed jobs (extract-facts / topic / summarize / classify) set their field with a
monkeypatched `prompt.run`, and HONEST-DEFER (field unset + `deferred`) when the engine is
unavailable / the router errors (SB-077); summarize never overwrites the raw `summary`;
advance-effects run the current stage's job then delegate the label bump to
`memory-admit.advance` (one owner of `stage`); DRY-RUN default; and `reconcile()` projects
the additive `enriched` coverage block.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
JAN_PATH = REPO_ROOT / "scripts" / "intelligence" / "memory-janitor.py"


def _load():
    spec = importlib.util.spec_from_file_location("memory_janitor", JAN_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


J = _load()
S = J._store  # the memory-store module the janitor reuses


@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "STORE", tmp_path / "store.json")
    monkeypatch.setattr(S, "CHANGES", tmp_path / "changes.json")
    monkeypatch.setattr(S, "SPAN_STORE", tmp_path / "spans.jsonl")
    monkeypatch.setattr(S, "MEMORY_STATE", tmp_path / "memory.json")
    monkeypatch.delenv("SOVEREIGN_OS_DRY_RUN", raising=False)
    return tmp_path


def _seed(entries: dict):
    S._atomic_write(S.STORE, {"entries": entries})


def _e(mid, typ, summary, *, stage="observe", state="active", created="2026-01-01T00:00:00+00:00"):
    return {"id": mid, "type": typ, "stage": stage, "summary": summary,
            "state": state, "created": created, "updated": created}


def _get(mid):
    return S._entries()[mid]


def _proj(store_dir):
    return json.loads((store_dir / "memory.json").read_text())


def _fake_prompt(monkeypatch, *events):
    monkeypatch.setattr(J, "_prompt", type("P", (), {
        "run": staticmethod(lambda text: iter(list(events)))})())


# ── dedup (R04711) ─────────────────────────────────────────────────────────────

def test_dedup_marks_later_keeps_earliest(store):
    _seed({
        "mem-a": _e("mem-a", 2, "deploy the router on gpu one", created="2026-01-01T00:00:00+00:00"),
        "mem-b": _e("mem-b", 2, "Deploy the  router on GPU one", created="2026-01-02T00:00:00+00:00"),
        "mem-c": _e("mem-c", 3, "a different memory entirely", created="2026-01-03T00:00:00+00:00"),
    })
    r = J.dedup(confirm=True)
    assert r["ok"] and r["count"] == 1
    assert _get("mem-a")["state"] == "active"       # earliest kept
    assert _get("mem-b")["state"] == "duplicate"    # later marked
    assert _get("mem-b")["dedup_of"] == "mem-a"
    assert _get("mem-c")["state"] == "active"        # distinct untouched


def test_dedup_never_hard_deletes_and_is_idempotent(store):
    _seed({
        "mem-a": _e("mem-a", 2, "same text", created="2026-01-01T00:00:00+00:00"),
        "mem-b": _e("mem-b", 2, "same text", created="2026-01-02T00:00:00+00:00"),
    })
    J.dedup(confirm=True)
    assert set(S._entries()) == {"mem-a", "mem-b"}   # both rows still present
    assert J.dedup(confirm=True)["count"] == 0        # nothing left active to dedup


def test_dedup_dry_run_no_mutation(store):
    _seed({"mem-a": _e("mem-a", 2, "x", created="2026-01-01T00:00:00+00:00"),
           "mem-b": _e("mem-b", 2, "x", created="2026-01-02T00:00:00+00:00")})
    r = J.dedup(confirm=False)
    assert r["dry_run"] and r["count"] == 1
    assert _get("mem-b")["state"] == "active"         # unchanged


def test_dedup_different_type_not_merged(store):
    _seed({"mem-a": _e("mem-a", 2, "same text"),
           "mem-b": _e("mem-b", 3, "same text", created="2026-01-02T00:00:00+00:00")})
    assert J.dedup(confirm=True)["count"] == 0


# ── tag (R04710) ───────────────────────────────────────────────────────────────

def test_tag_deterministic_and_idempotent(store):
    _seed({"mem-a": _e("mem-a", 3, "router latency spiked during the eval run")})
    r1 = J.tag("mem-a", confirm=True)
    assert r1["ok"] and "router" in r1["value"] and "latency" in r1["value"]
    assert r1["value"] == sorted(r1["value"])          # deterministic order
    r2 = J.tag("mem-a", confirm=True)
    assert r2["value"] == r1["value"]                  # idempotent


def test_tag_dry_run_no_write(store):
    _seed({"mem-a": _e("mem-a", 3, "hello world of memory")})
    assert J.tag("mem-a", confirm=False)["dry_run"] is True
    assert "tags" not in _get("mem-a")


def test_tag_unknown_id(store):
    _seed({})
    assert J.tag("mem-x", confirm=True)["ok"] is False


# ── graph-edges (R04713) ───────────────────────────────────────────────────────

def test_edges_links_token_overlap_bidirectional(store):
    _seed({
        "mem-a": _e("mem-a", 2, "the router failed on gpu one"),
        "mem-b": _e("mem-b", 2, "gpu one router restarted cleanly", created="2026-01-02T00:00:00+00:00"),
        "mem-c": _e("mem-c", 3, "totally unrelated grocery list", created="2026-01-03T00:00:00+00:00"),
    })
    r = J.edges(confirm=True)
    assert r["ok"] and r["count"] == 1
    assert any(x["to"] == "mem-b" for x in _get("mem-a")["edges"])
    assert any(x["to"] == "mem-a" for x in _get("mem-b")["edges"])   # bidirectional
    assert "edges" not in _get("mem-c")                              # unrelated unlinked


def test_edges_idempotent(store):
    _seed({"mem-a": _e("mem-a", 2, "router gpu one memory"),
           "mem-b": _e("mem-b", 2, "router gpu one memory again", created="2026-01-02T00:00:00+00:00")})
    J.edges(confirm=True)
    before = json.dumps(_get("mem-a")["edges"], sort_keys=True)
    assert J.edges(confirm=True)["edges_added"] == 0
    assert json.dumps(_get("mem-a")["edges"], sort_keys=True) == before


# ── SLM-routed jobs (SDD-062 engine; honest-defer per SB-077) ──────────────────

def test_slm_topic_sets_field(store, monkeypatch):
    _seed({"mem-a": _e("mem-a", 3, "router latency on gpu one")})
    _fake_prompt(monkeypatch, {"type": "token", "text": "network "},
                 {"type": "token", "text": "diagnostics"}, {"type": "done"})
    r = J._slm_one("topic", "mem-a", confirm=True)
    assert r["ok"] and r["field"] == "topic" and r["value"] == "network diagnostics"
    assert _get("mem-a")["topic"] == "network diagnostics"


def test_slm_extract_facts_list(store, monkeypatch):
    _seed({"mem-a": _e("mem-a", 3, "a memory")})
    _fake_prompt(monkeypatch, {"type": "token", "text": "- fact one\n- fact two"},
                 {"type": "done"})
    r = J._slm_one("extract-facts", "mem-a", confirm=True)
    assert r["value"] == ["fact one", "fact two"]
    assert _get("mem-a")["derived_facts"] == ["fact one", "fact two"]


def test_slm_summarize_never_overwrites_raw_summary(store, monkeypatch):
    _seed({"mem-a": _e("mem-a", 3, "the original raw summary text")})
    _fake_prompt(monkeypatch, {"type": "token", "text": "short form"}, {"type": "done"})
    J._slm_one("summarize", "mem-a", confirm=True)
    assert _get("mem-a")["summary"] == "the original raw summary text"   # raw preserved
    assert _get("mem-a")["summary_short"] == "short form"


def test_slm_honest_defer_engine_unavailable(store, monkeypatch):
    _seed({"mem-a": _e("mem-a", 3, "a memory")})
    monkeypatch.setattr(J, "_prompt", None)             # no engine
    r = J._slm_one("topic", "mem-a", confirm=True)
    assert r["ok"] and r["deferred"] is True            # deferring is a correct outcome
    assert "topic" not in _get("mem-a")                 # field left unset (SB-077)


def test_slm_honest_defer_on_router_error(store, monkeypatch):
    _seed({"mem-a": _e("mem-a", 3, "a memory")})
    _fake_prompt(monkeypatch, {"type": "error", "error": "router unreachable at 127.0.0.1:8080"})
    r = J._slm_one("classify", "mem-a", confirm=True)
    assert r["deferred"] is True and "unreachable" in r["reason"]
    assert "failure_class" not in _get("mem-a")


def test_slm_dry_run_does_not_call_engine(store, monkeypatch):
    _seed({"mem-a": _e("mem-a", 3, "a memory")})

    def _boom(text):
        raise AssertionError("SLM must not be called in DRY-RUN")

    monkeypatch.setattr(J, "_prompt", type("P", (), {"run": staticmethod(_boom)})())
    r = J._slm_one("topic", "mem-a", confirm=False)
    assert r["dry_run"] is True and "topic" not in _get("mem-a")


# ── advance-effects (delegates the label bump; one owner of `stage`) ───────────

def test_advance_runs_stage_effect_then_bumps_label(store):
    # at `classify` the effect is tag; then the label advances classify→quarantine.
    _seed({"mem-a": _e("mem-a", 3, "router latency spiked", stage="classify")})
    r = J.advance("mem-a", confirm=True)
    assert r["ok"] and r["advance"]["stage"] == "quarantine"
    assert "tags" in _get("mem-a") and _get("mem-a")["stage"] == "quarantine"


def test_advance_verify_stage_sets_flag(store):
    _seed({"mem-a": _e("mem-a", 3, "a memory", stage="verify")})
    r = J.advance("mem-a", confirm=True)
    assert _get("mem-a")["verified"] is True
    assert r["advance"]["stage"] == "promote"


def test_advance_slm_defer_does_not_block_label(store, monkeypatch):
    # extract-facts stage effect defers (no engine) but the label still advances.
    _seed({"mem-a": _e("mem-a", 3, "a memory", stage="extract-facts")})
    monkeypatch.setattr(J, "_prompt", None)
    r = J.advance("mem-a", confirm=True)
    assert r["effect"]["deferred"] is True
    assert r["advance"]["stage"] == "verify"             # label progressed regardless
    assert "derived_facts" not in _get("mem-a")


def test_advance_dry_run_no_mutation(store):
    _seed({"mem-a": _e("mem-a", 3, "x", stage="classify")})
    J.advance("mem-a", confirm=False)
    assert _get("mem-a")["stage"] == "classify" and "tags" not in _get("mem-a")


# ── reconcile enriched projection (SDD-066) ────────────────────────────────────

def test_reconcile_projects_enriched_block(store, monkeypatch):
    _seed({
        "mem-a": _e("mem-a", 2, "one"),
        "mem-b": _e("mem-b", 2, "two", created="2026-01-02T00:00:00+00:00"),
    })
    _fake_prompt(monkeypatch, {"type": "token", "text": "topicX"}, {"type": "done"})
    J._slm_one("topic", "mem-a", confirm=True)
    J.tag("mem-b", confirm=True)
    proj = _proj(store)
    assert "enriched" in proj
    assert proj["enriched"]["with_topic"] == 1
    # counts + lifecycle still projected (not clobbered by the additive block).
    assert "counts" in proj and "lifecycle" in proj


def test_reconcile_counts_duplicates_separately(store):
    _seed({
        "mem-a": _e("mem-a", 2, "dup"),
        "mem-b": _e("mem-b", 2, "dup", created="2026-01-02T00:00:00+00:00"),
    })
    J.dedup(confirm=True)
    proj = _proj(store)
    assert proj["enriched"]["duplicates"] == 1
    assert proj["counts"]["episodic"] == 1              # the marked dup drops from counts


# ── sweep (SDD-070 — recurrent maintenance pass) ───────────────────────────────

def _stage(mid):
    return S._entries()[mid]["stage"]


def test_sweep_enriches_and_advances_one_step(store, monkeypatch):
    _seed({"mem-a": _e("mem-a", 2, "router failed on gpu one", stage="observe"),
           "mem-b": _e("mem-b", 3, "deploy notes for the router", stage="observe",
                       created="2026-01-02T00:00:00+00:00")})
    monkeypatch.setattr(J, "_prompt", None)   # SLM honest-defers; deterministic still runs
    r = J.sweep(confirm=True)
    assert r["ok"] and r["swept"] == 2 and r["tagged"] == 2 and r["advanced"] == 2
    assert _stage("mem-a") == "classify" and "tags" in S._entries()["mem-a"]  # one step + enriched


def test_sweep_stops_at_verify_and_never_promotes(store, monkeypatch):
    _seed({"mem-v": _e("mem-v", 2, "already at verify", stage="verify")})
    monkeypatch.setattr(J, "_prompt", None)
    r = J.sweep(confirm=True)
    assert r["verified_at_stop"] == 1
    assert S._entries()["mem-v"]["verified"] is True    # verify effect applied at the stop
    assert _stage("mem-v") == "verify"                  # NOT advanced to promote


def test_sweep_walks_to_verify_then_halts(store, monkeypatch):
    _seed({"mem-a": _e("mem-a", 2, "a memory", stage="observe")})
    monkeypatch.setattr(J, "_prompt", None)
    for _ in range(12):
        J.sweep(confirm=True)
    assert _stage("mem-a") == "verify"                  # walked up and halted at the stop
    assert S._entries()["mem-a"].get("verified") is True
    assert _stage("mem-a") != "promote"                 # never auto-promoted


def test_sweep_leaves_operator_advanced_entries_untouched(store, monkeypatch):
    _seed({"mem-p": _e("mem-p", 2, "operator advanced", stage="promote")})
    monkeypatch.setattr(J, "_prompt", None)
    J.sweep(confirm=True)
    assert _stage("mem-p") == "promote"                 # past the stop — untouched
    assert "verified" not in S._entries()["mem-p"]


def test_sweep_skips_duplicates(store, monkeypatch):
    _seed({"mem-a": _e("mem-a", 2, "same text", stage="observe"),
           "mem-b": _e("mem-b", 2, "same text", stage="observe",
                       created="2026-01-02T00:00:00+00:00")})
    monkeypatch.setattr(J, "_prompt", None)
    r = J.sweep(confirm=True)
    assert r["deduped"] == 1
    assert S._entries()["mem-b"]["state"] == "duplicate"
    # the duplicate is not in the active sweep set → not advanced.
    assert _stage("mem-b") == "observe"


def test_sweep_slm_enriches_when_router_available(store, monkeypatch):
    _seed({"mem-a": _e("mem-a", 2, "a memory", stage="observe")})
    _fake_prompt(monkeypatch, {"type": "token", "text": "netops"}, {"type": "done"})
    J.sweep(confirm=True)
    e = S._entries()["mem-a"]
    assert e.get("topic") == "netops" and e.get("summary_short") == "netops"


def test_sweep_dry_run_mutates_nothing(store, monkeypatch):
    _seed({"mem-a": _e("mem-a", 2, "a memory", stage="observe")})
    monkeypatch.setattr(J, "_prompt", None)
    r = J.sweep(confirm=False)
    assert r["dry_run"] is True and r["advanced"] == 0
    assert _stage("mem-a") == "observe" and "tags" not in S._entries()["mem-a"]


def test_sweep_unknown_stop_stage_rejected(store):
    _seed({"mem-a": _e("mem-a", 2, "x")})
    assert J.sweep(confirm=True, stop="bogus")["ok"] is False
