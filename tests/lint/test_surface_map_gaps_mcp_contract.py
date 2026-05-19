"""R545 (E5++) — surface-map gaps MCP tool contract lint.

Exposes the parameterless `surface-map gaps --json` (default
threshold=3) over MCP as a §1g delivery-regression detector.

Post-R539 steady state: count=0 (ALL modules at structural ceiling).
The tool's value is FAST REGRESSION DETECTION: any non-empty
`below_threshold` list signals drift from the historic ceiling-
closure state. Agents auditing §1g coverage can check the entire
system with one MCP call.

Per operator §1g 8-surface delivery contract anchor verbatim (R453):

  "everything is not just core, not just cli, not just TUI, not just
   API, not just tool and MCP but also Dashboards and Web Apps and
   Services"

Ceiling-promotion rule (R286 / R532): runtime-argument variants
(`gaps --threshold N --module <m>`) stay CLI-only — only the
parameterless default-threshold rollup is exposed via MCP.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MCP_AGG = REPO_ROOT / "scripts" / "interop" / "mcp-aggregate.py"
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"

TOOL_NAME = "surface-map-gaps"


def _load_mcp_aggregate():
    spec = importlib.util.spec_from_file_location("_mcp_agg", MCP_AGG)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_mcp_tool_registered():
    mod = _load_mcp_aggregate()
    names = {t["name"] for t in mod.LOCAL_TOOLS}
    assert TOOL_NAME in names, (
        f"R545: MCP aggregator must register {TOOL_NAME!r}"
    )


def test_mcp_tool_fixed_argv_shape_r286():
    mod = _load_mcp_aggregate()
    tool = next(t for t in mod.LOCAL_TOOLS if t["name"] == TOOL_NAME)
    argv = tool["argv"]
    assert argv[0] == "sovereign-osctl"
    assert argv[1] == "surface-map"
    assert argv[2] == "gaps"
    assert argv[-1] == "--json"
    assert "--threshold" not in argv, (
        f"R545: {TOOL_NAME} argv must NOT include --threshold "
        f"(per-call args stay CLI-only); got {argv}"
    )
    assert "--module" not in argv, (
        f"R545: {TOOL_NAME} argv must NOT include --module "
        f"(per-call args stay CLI-only); got {argv}"
    )
    for arg in argv:
        assert "<" not in arg and ">" not in arg


def test_mcp_tool_summary_substantive_and_cites_r539():
    """The summary MUST frame the tool as a regression detector,
    cite the R539 historic ceiling-closure (the baseline against
    which drift is detected), and surface the operator-§1g UX rule."""
    mod = _load_mcp_aggregate()
    tool = next(t for t in mod.LOCAL_TOOLS if t["name"] == TOOL_NAME)
    summary = tool.get("summary", "")
    assert len(summary) >= 80, f"summary too thin: {summary!r}"
    low = summary.lower()
    assert "regression" in low, (
        "summary must frame the tool as a regression detector"
    )
    assert "r539" in low, "summary must cite R539 baseline"
    assert "ceiling" in low
    assert "read-only" in low or "read only" in low
    # The CLI-only carve-out must surface so agents understand why
    # `--threshold` / `--module` aren't on the MCP surface.
    assert "cli-only" in low or "r286" in low or "r532" in low, (
        f"summary must reference the CLI-only ceiling rule; "
        f"got {summary!r}"
    )


def test_mcp_tool_end_to_end_smoke_returns_baseline_shape():
    """Invoking the MCP argv MUST produce the operator-named gaps
    payload shape: threshold + count + below_threshold[] +
    at_structural_ceiling{}."""
    mod = _load_mcp_aggregate()
    tool = next(t for t in mod.LOCAL_TOOLS if t["name"] == TOOL_NAME)
    argv = list(tool["argv"])
    argv[0] = str(OSCTL)
    argv.insert(0, "bash")
    cp = subprocess.run(
        argv, capture_output=True, text=True, timeout=15,
        env={"PATH": "/usr/bin:/bin", "HOME": "/tmp"},
    )
    assert cp.returncode == 0, cp.stderr[:300]
    payload = json.loads(cp.stdout)
    assert isinstance(payload, dict)
    for key in ("threshold", "count", "below_threshold"):
        assert key in payload, (
            f"R545: gaps payload missing key {key!r}; "
            f"got {sorted(payload.keys())}"
        )
    assert isinstance(payload["below_threshold"], list)
    assert isinstance(payload["count"], int)
    assert isinstance(payload["threshold"], int)
    assert payload["threshold"] == 3, (
        f"R545: default-threshold MCP tool must use the surface-map "
        f"default threshold=3; got {payload['threshold']}"
    )


def test_mcp_tool_post_r539_steady_state_is_count_zero():
    """Post-R539 the §1g delivery-gap roster MUST be empty (ALL
    modules at structural ceiling). Failure of this test would
    indicate REAL §1g delivery regression — exactly the use case
    R545 exposes via MCP."""
    mod = _load_mcp_aggregate()
    tool = next(t for t in mod.LOCAL_TOOLS if t["name"] == TOOL_NAME)
    argv = list(tool["argv"])
    argv[0] = str(OSCTL)
    argv.insert(0, "bash")
    cp = subprocess.run(
        argv, capture_output=True, text=True, timeout=15,
        env={"PATH": "/usr/bin:/bin", "HOME": "/tmp"},
    )
    payload = json.loads(cp.stdout)
    assert payload["count"] == 0, (
        f"R539 invariant: count must be 0 post-historic-ceiling-"
        f"closure; got count={payload['count']} below_threshold="
        f"{payload.get('below_threshold')}"
    )
    assert payload["below_threshold"] == [], (
        "R539 invariant: below_threshold must be empty"
    )


def test_mcp_tool_categories_anchor_regression_detection():
    mod = _load_mcp_aggregate()
    tool = next(t for t in mod.LOCAL_TOOLS if t["name"] == TOOL_NAME)
    cats = set(tool.get("categories", []))
    assert "surface-map" in cats
    assert "gaps" in cats
    assert "regression-detection" in cats, (
        f"R545: categories must include 'regression-detection'; "
        f"got {sorted(cats)}"
    )
