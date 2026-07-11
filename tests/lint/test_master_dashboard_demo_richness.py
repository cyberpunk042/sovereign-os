"""master-dashboard DEMO richness lint (SDD-134).

The master-dashboard is the cockpit front door; its opt-in DEMO must read as a
BUSY, HEALTHY box, not a bare 3-route stub (the operator caught the thin
SDD-129 demo: "the screenshot you showed is a bad Demo no?"). This pins the
enrichment floor so it can't silently regress:
  - DEMO_MASTER carries a populated front door (>=6 routes, health parity,
    a multi-category catalog with mixed statuses, control systems, m060 artifacts),
  - the four health banners + the M060 grid fetchers are demo-gated (so they read
    healthy from sample data, zero network — SB-077 / R10212 preserved).
Everything stays badged + `demo/`-prefixed (never confusable with live telemetry).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PANEL = REPO / "webapp" / "master-dashboard" / "index.html"


def _body() -> str:
    return PANEL.read_text(encoding="utf-8")


def _demo_master() -> dict:
    body = _body()
    m = re.search(r"const DEMO_MASTER = (\{.*?\n\});", body, re.DOTALL)
    assert m, "DEMO_MASTER constant not found"
    # JS object-literal → JSON: quote the bare keys, drop trailing commas.
    src = m.group(1)
    src = re.sub(r"([{,]\s*)([A-Za-z_][\w-]*)\s*:", r'\1"\2":', src)
    src = re.sub(r'"(/[^"]*)":', lambda mo: '"' + mo.group(1) + '":', src)  # keep path keys
    # the path-string keys are already quoted; the regex above only touches bare keys
    src = re.sub(r",(\s*[}\]])", r"\1", src)
    return json.loads(src)


def test_demo_master_is_a_busy_healthy_front_door():
    dm = _demo_master()
    routes = dm["/routes"]["routes"]
    assert len(routes) >= 6, f"DEMO front door must show a busy route table (>=6), got {len(routes)}"
    assert dm["/routes"]["count"] == len(routes), "route count must match the route list"
    health = dm["/health"]
    assert health["reachable"] == health["count"] == len(routes), "DEMO shows every route reachable (healthy)"
    assert len(dm["/discover"]["discovered"]) >= 3, "DEMO must show discovered selfdef manifests"
    cat = dm["/catalog"]
    assert len(cat["categories"]) >= 3, "DEMO catalog must span multiple categories"
    assert len(cat["dashboards"]) >= 6, "DEMO catalog must list a full set of dashboards"
    statuses = {d.get("status") for d in cat["dashboards"]}
    assert {"live", "snapshot", "planned"} <= statuses, f"DEMO catalog must mix live/snapshot/planned, got {statuses}"
    assert len(dm["/control-systems"]["systems"]) >= 6, "DEMO coverage must show control systems"
    assert len(dm["/api/m060/health"]["artifacts"]) >= 6, "DEMO m060 health must carry fresh artifacts for the grid"


def test_all_demo_ids_are_obviously_placeholder():
    dm = _demo_master()
    for r in dm["/routes"]["routes"]:
        assert r["slug"].startswith("demo/"), f"route slug must be demo/-prefixed: {r['slug']}"
    for d in dm["/discover"]["discovered"]:
        assert d["slug"].startswith("demo/"), f"discovered slug must be demo/-prefixed: {d['slug']}"


def test_health_banners_and_grid_are_demo_gated():
    body = _body()
    # each direct-fetch banner short-circuits to DEMO_MASTER before any network call
    for needle in (
        'if (demoActive()) { payload = DEMO_MASTER["/api/m060/health"]; }',
        'if (demoActive()) { payload = DEMO_MASTER["/api/ms022/sse-quota"]; }',
        'if (demoActive()) { payload = DEMO_MASTER["/api/four-watchdog/state"]; }',
    ):
        assert needle in body, f"a health banner is not demo-gated: {needle}"
    assert "DEMO_M060_MIRROR" in body, "the M060 per-mirror grid must have a demo online sample"
    assert "if (demoActive()) return {id: m.id" in body, "fetchMirrorStatus must short-circuit in demo (zero network)"
    assert "for (const a of (DEMO_MASTER[\"/api/m060/health\"].artifacts" in body, (
        "fetchM060ArtifactHealthMap must build its map from DEMO_MASTER in demo (zero network)"
    )
