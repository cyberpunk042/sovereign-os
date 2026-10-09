"""model-health must never dress catalog candidates up as resident models.

The 2026-10-09 D-21 incident: a runtime-profile switch restarted the GPU
tiers; while each tier was unreachable, publish-model-state.py correctly
dropped it from `loaded` ("a stopped tier disappears rather than lingering
as a claim") — but model-health.snapshot() then fell through to the catalog
fallback PER ROLE, so D-21 rendered "oracle GPU0 · idle gpt-oss-120b" and
"logic GPU1 · idle Qwen-32B-Ternary-Quant" beside "profile expects:
<the model actually loading>". The operator read it as the model load
resetting to defaults. It never had: the processes were correct the whole
time; the fallback branch lied.

Contract proven here:
  * witness published (model-state.json exists) + role missing  -> models
    empty, model_source "unresident" — NEVER catalog rows;
  * witness published with a non-empty loaded set + one role
    missing      -> that role is "unresident", the others stay "runtime";
  * no witness at all (publisher not installed)                 -> the
    documented catalog fallback still answers, model_source "catalog".
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "scripts" / "inference" / "model-health.py"

# The subset parser expects `models:` at indent 2, entries at 4, fields at 6.
CATALOG = """schema_version: "1.0.0"
catalog:
  description: |
    fixture
  models:
    - id: Fixture-Logic-LM
      tier: logic
      class: llm
      status: verified-real
    - id: Fixture-Oracle-LM
      tier: oracle
      class: llm
      status: verified-real
"""


def _snapshot(tmp_path: Path, state: dict | None) -> dict:
    catalog = tmp_path / "catalog.yaml"
    catalog.write_text(CATALOG, encoding="utf-8")
    env = {
        "SOVEREIGN_OS_MODEL_CATALOG": str(catalog),
        "SOVEREIGN_OS_MODEL_STATE": str(tmp_path / "model-state.json"),
        "SOVEREIGN_OS_MODEL_LATENCY": str(tmp_path / "model-latency.json"),
    }
    if state is not None:
        (tmp_path / "model-state.json").write_text(json.dumps(state), encoding="utf-8")
    r = subprocess.run(
        ["python3", str(CORE), "status", "--json"],
        capture_output=True, text=True, timeout=60, env=env,
    )
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_published_witness_never_resurrects_catalog(tmp_path):
    """Empty published `loaded` => roles report absence, not candidates."""
    snap = _snapshot(tmp_path, {"loaded": {}, "updated_ts": "x"})
    for role in ("logic", "oracle"):
        entry = snap["roles"][role]
        assert entry["models"] == [], f"{role}: catalog candidate resurrected"
        assert entry["model_source"] == "unresident"
        assert entry["loaded_count"] == 0
    assert snap["summary"]["source"] == "unresident"


def test_partial_witness_unresidents_only_the_missing_roles(tmp_path):
    """Mid-restart window: one tier answering, one not — only the missing
    role reports absence; the answering role keeps its runtime row."""
    oracle_row = {"id": "Fixture-Oracle-LM", "precision": "q4"}
    snap = _snapshot(tmp_path, {"loaded": {"oracle": [oracle_row]}})
    assert snap["roles"]["oracle"]["models"][0]["id"] == "Fixture-Oracle-LM"
    assert snap["roles"]["oracle"]["model_source"] == "runtime"
    logic = snap["roles"]["logic"]
    assert logic["models"] == []
    assert logic["model_source"] == "unresident"
    # The catalog fixture row must appear NOWHERE in the roles output.
    assert "Fixture-Logic-LM" not in json.dumps(snap["roles"])


def test_no_witness_keeps_the_documented_catalog_fallback(tmp_path):
    """Publisher never installed (no model-state.json at all): the catalog
    fallback remains the honest degraded mode, labelled `catalog`."""
    snap = _snapshot(tmp_path, None)
    assert snap["roles"]["oracle"]["model_source"] == "catalog"
    assert snap["roles"]["oracle"]["models"][0]["id"] == "Fixture-Oracle-LM"
    assert snap["summary"]["source"] == "catalog"
