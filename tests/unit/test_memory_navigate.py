"""Unit tests for the SDD-068 M028 RLM memory navigator
`scripts/intelligence/memory-navigate.py` (M00472) + the M00469 temporal query verbs.

Covers: deterministic slice selection (rank by query relevance; --type/--stage/--topic
filters; --limit; no-match); the agentic child-calls + compose path (monkeypatched LM);
honest-defer (LM unreachable → slices WITHOUT a composed answer; empty store → empty);
--no-compose skips the LM; each of the 5 M00469 temporal verbs (changed / true-then /
true-now / last-verified real-substrate; contradicted-by → deferred/empty per SB-077); and
the READ-COMPUTE invariant — the store file is byte-identical after a navigate.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
NAV_PATH = REPO_ROOT / "scripts" / "intelligence" / "memory-navigate.py"


def _load():
    spec = importlib.util.spec_from_file_location("memory_navigate", NAV_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


N = _load()
S = N._store  # the memory-store module the navigator reads


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


def _e(mid, typ, summary, *, stage="observe", state="active",
       created="2026-01-01T00:00:00+00:00", updated=None, **extra):
    d = {"id": mid, "type": typ, "stage": stage, "summary": summary, "state": state,
         "created": created, "updated": updated or created}
    d.update(extra)
    return d


def _fake_prompt(monkeypatch, *events):
    monkeypatch.setattr(N, "_prompt", type("P", (), {
        "run": staticmethod(lambda text: iter(list(events)))})())


def _seed_router_set():
    _seed({
        "mem-a": _e("mem-a", 2, "router failed on gpu one after a dependency bump",
                    stage="verify", created="2026-01-01T00:00:00+00:00",
                    updated="2026-01-05T00:00:00+00:00", topic="networking",
                    tags=["router", "gpu", "dependency"],
                    derived_facts=["router crashed post-upgrade"], verified=True),
        "mem-b": _e("mem-b", 3, "grocery list milk eggs bread",
                    created="2026-01-02T00:00:00+00:00"),
        "mem-c": _e("mem-c", 2, "gpu one router restart fixed the dependency issue",
                    stage="link", created="2026-01-03T00:00:00+00:00", topic="networking",
                    tags=["router", "gpu"]),
    })


# ── deterministic slice selection ──────────────────────────────────────────────

def test_rank_selects_relevant_excludes_unrelated(store):
    _seed_router_set()
    r = N.navigate("router gpu dependency", compose=False)
    ids = [s["id"] for s in r["slices"]]
    assert "mem-a" in ids and "mem-c" in ids and "mem-b" not in ids  # grocery excluded


def test_type_filter(store):
    _seed_router_set()
    ids = [s["id"] for s in N.navigate("router", mtype=2, compose=False)["slices"]]
    assert set(ids) == {"mem-a", "mem-c"}   # type 3 grocery excluded


def test_topic_and_stage_filters(store):
    _seed_router_set()
    assert {s["id"] for s in N.navigate("", topic="network", compose=False)["slices"]} == {"mem-a", "mem-c"}
    assert [s["id"] for s in N.navigate("", stage="verify", compose=False)["slices"]] == ["mem-a"]


def test_limit_caps_results(store):
    _seed_router_set()
    assert N.navigate("router gpu dependency", limit=1, compose=False)["count"] == 1


def test_no_match_empty(store):
    _seed_router_set()
    r = N.navigate("nonexistent zzz", compose=False)
    assert r["count"] == 0 and r["slices"] == []


def test_slice_view_is_not_a_full_dump(store):
    # R04700 — the response projects a compact slice, not the raw entry.
    _seed_router_set()
    s = N.navigate("router", compose=False)["slices"][0]
    assert set(s) == {"id", "type", "stage", "summary", "topic", "tags",
                      "derived_facts", "edges", "created", "updated"}
    assert isinstance(s["edges"], int)   # edge COUNT, not the raw edge list


# ── agentic child-calls + compose ──────────────────────────────────────────────

def test_compose_produces_answer_from_findings(store, monkeypatch):
    _seed_router_set()
    _fake_prompt(monkeypatch, {"type": "token", "text": "a restart fixed the router"},
                 {"type": "done"})
    r = N.navigate("router dependency")
    assert r["answer"] == "a restart fixed the router" and r["composed"] is True
    # one finding per selected slice (child calls over slices, R04703).
    assert len(r["findings"]) == r["count"] and r["count"] >= 1


def test_no_compose_skips_the_lm(store, monkeypatch):
    _seed_router_set()

    def _boom(text):
        raise AssertionError("LM must not be called with --no-compose")

    monkeypatch.setattr(N, "_prompt", type("P", (), {"run": staticmethod(_boom)})())
    r = N.navigate("router", compose=False)
    assert r["composed"] is False and r["answer"] is None and r["count"] >= 1


# ── honest-defer (SB-077) ──────────────────────────────────────────────────────

def test_honest_defer_when_lm_unavailable(store, monkeypatch):
    _seed_router_set()
    monkeypatch.setattr(N, "_prompt", None)
    r = N.navigate("router dependency")
    assert r["deferred"] is True and r["answer"] is None
    assert r["count"] >= 1 and r["slices"]          # slices STILL returned, honestly


def test_honest_defer_on_router_error(store, monkeypatch):
    _seed_router_set()
    _fake_prompt(monkeypatch, {"type": "error", "error": "router unreachable at 127.0.0.1:8080"})
    r = N.navigate("router dependency")
    assert r["deferred"] is True and "unreachable" in r["reason"] and r["answer"] is None


def test_empty_store_empty_result(store, monkeypatch):
    _seed({})
    _fake_prompt(monkeypatch, {"type": "token", "text": "x"}, {"type": "done"})
    r = N.navigate("anything")
    assert r["ok"] and r["count"] == 0 and r["answer"] is None


# ── M00469 temporal verbs ──────────────────────────────────────────────────────

def test_verb_changed(store):
    _seed_router_set()   # mem-a has updated != created
    ids = [s["id"] for s in N.navigate("", verb="changed", compose=False)["slices"]]
    assert ids == ["mem-a"]


def test_verb_true_now_is_active_set(store):
    _seed_router_set()
    assert N.navigate("", verb="true-now", compose=False)["count"] == 3


def test_verb_true_then_requires_at_and_filters_by_created(store):
    _seed_router_set()
    err = N.navigate("", verb="true-then", compose=False)
    assert err["ok"] is False and "--at" in err["error"]
    r = N.navigate("", verb="true-then", at="2026-01-02T12:00:00+00:00", compose=False)
    assert set(s["id"] for s in r["slices"]) == {"mem-a", "mem-b"}   # created <= T; mem-c (01-03) out
    assert "temporal_note" in r


def test_verb_last_verified_sorts_by_verified_at(store):
    # SDD-101 — real verified_at timestamps, newest first.
    _seed({
        "mem-a": _e("mem-a", 2, "older verify", verified=True,
                    verified_at="2026-01-01T00:00:00+00:00"),
        "mem-b": _e("mem-b", 2, "newer verify", created="2026-01-02T00:00:00+00:00",
                    verified=True, verified_at="2026-02-01T00:00:00+00:00"),
        "mem-c": _e("mem-c", 2, "unverified", created="2026-01-03T00:00:00+00:00"),
    })
    r = N.navigate("", verb="last-verified", compose=False)
    assert [s["id"] for s in r["slices"]] == ["mem-b", "mem-a"]   # newest verified_at first
    assert "SDD-101" in r["temporal_note"]


def test_verb_contradicted_by_returns_real_edges(store):
    # SDD-101 — real result from `contradicts` edges (not deferred).
    _seed({
        "mem-a": _e("mem-a", 2, "router failed", edges=[{"to": "mem-b", "kind": "contradicts"}]),
        "mem-b": _e("mem-b", 2, "router works", created="2026-01-02T00:00:00+00:00",
                    edges=[{"to": "mem-a", "kind": "contradicts"}]),
        "mem-c": _e("mem-c", 2, "unrelated", created="2026-01-03T00:00:00+00:00",
                    edges=[{"to": "mem-a", "kind": "related"}]),
    })
    r = N.navigate("", verb="contradicted-by", compose=False)
    assert not r.get("deferred")                      # real, not honest-defer
    assert {s["id"] for s in r["slices"]} == {"mem-a", "mem-b"}   # mem-c (related-only) excluded


def test_verb_contradicted_by_empty_is_honest_not_deferred(store):
    _seed_router_set()   # no contradicts edges
    r = N.navigate("", verb="contradicted-by", compose=False)
    assert not r.get("deferred") and r["count"] == 0   # honestly empty, not "substrate absent"


def test_verb_contradicted_by_target_filter(store):
    _seed({
        "mem-a": _e("mem-a", 2, "a", edges=[{"to": "mem-b", "kind": "contradicts"}]),
        "mem-x": _e("mem-x", 2, "x", created="2026-01-02T00:00:00+00:00",
                    edges=[{"to": "mem-z", "kind": "contradicts"}]),
    })
    r = N.navigate("", verb="contradicted-by", at="mem-b", compose=False)
    assert [s["id"] for s in r["slices"]] == ["mem-a"]   # only the one contradicting mem-b


def test_unknown_verb_rejected(store):
    _seed_router_set()
    assert N.navigate("", verb="bogus")["ok"] is False


# ── the READ-COMPUTE invariant ─────────────────────────────────────────────────

def test_navigate_never_mutates_the_store(store, monkeypatch):
    _seed_router_set()
    before = hashlib.sha256((store / "store.json").read_bytes()).hexdigest()
    _fake_prompt(monkeypatch, {"type": "token", "text": "answer"}, {"type": "done"})
    N.navigate("router dependency")                       # compose path (LM called)
    N.navigate("", verb="changed", compose=False)          # temporal path
    N.navigate("", verb="contradicted-by")                 # defer path
    after = hashlib.sha256((store / "store.json").read_bytes()).hexdigest()
    assert before == after                                 # byte-identical — read-only
