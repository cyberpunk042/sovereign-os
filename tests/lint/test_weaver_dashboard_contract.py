"""R496 (master spec § 21) — Weaver Grafana dashboard contract lint.

Closes the weaver dashboard:FUTURE waiver and registers `weaver` as a
first-class MODULE_COVERAGE entry (3 surfaces: core / cli / dashboard).

Per operator §1g verbatim (sacrosanct):

  "We do not minimize anything."

The Weaver (master spec § 21) is the operator-§21 Atomic State Transition
Protocol — the lockless-loopback ZFS-layer atomic-rename primitive that
commits state-fabric files (IDENTITY/SOUL/AGENTS/CLAUDE) without
filesystem lag or concurrent-write collisions.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WEAVER_DASHBOARD_JSON = (
    REPO_ROOT / "docs" / "observability" / "dashboards"
    / "sovereign-os-weaver.json"
)


def test_dashboard_json_exists():
    assert WEAVER_DASHBOARD_JSON.is_file(), (
        f"missing weaver dashboard: {WEAVER_DASHBOARD_JSON}"
    )


def test_dashboard_json_parseable():
    data = json.loads(WEAVER_DASHBOARD_JSON.read_text(encoding="utf-8"))
    assert "panels" in data
    assert data.get("title")
    assert data.get("uid")


def test_dashboard_references_atomic_write_total_metric():
    body = WEAVER_DASHBOARD_JSON.read_text(encoding="utf-8")
    assert "sovereign_os_weaver_atomic_write_total" in body, (
        "weaver dashboard doesn't reference atomic_write_total metric"
    )


def test_dashboard_references_atomic_write_bytes_metric():
    body = WEAVER_DASHBOARD_JSON.read_text(encoding="utf-8")
    assert "sovereign_os_weaver_atomic_write_bytes" in body, (
        "weaver dashboard missing atomic_write_bytes payload-size metric"
    )


def test_dashboard_references_freshness_gauge():
    body = WEAVER_DASHBOARD_JSON.read_text(encoding="utf-8")
    assert "sovereign_os_weaver_atomic_write_last_timestamp" in body, (
        "weaver dashboard missing last_timestamp freshness gauge"
    )


def test_dashboard_documents_four_state_files():
    """Master spec § 7.1 4-file state-fabric ladder MUST appear verbatim
    in the §21 panel (operator-sacrosanct: IDENTITY / SOUL / AGENTS /
    CLAUDE)."""
    body = WEAVER_DASHBOARD_JSON.read_text(encoding="utf-8")
    for fname in ("IDENTITY.md", "SOUL.md", "AGENTS.md", "CLAUDE.md"):
        assert fname in body, (
            f"weaver dashboard missing state-fabric file: {fname!r}"
        )


def test_dashboard_documents_atomic_write_primitives():
    """Master spec § 21.1 atomic-write primitive vocabulary MUST appear
    (O_DIRECT / O_SYNC / O_TRUNC / atomic rename / 4K-aligned)."""
    body = WEAVER_DASHBOARD_JSON.read_text(encoding="utf-8")
    for primitive in ("O_DIRECT", "O_SYNC", "O_TRUNC",
                      "atomic rename", "4K-aligned"):
        assert primitive in body, (
            f"weaver dashboard missing § 21.1 primitive: {primitive!r}"
        )


def test_dashboard_quotes_master_spec_section_21_verbatim():
    """Master spec § 21 'lockless loopback write sequence on the ZFS layer'
    MUST appear verbatim — load-bearing protocol identity."""
    body = WEAVER_DASHBOARD_JSON.read_text(encoding="utf-8")
    assert "lockless loopback write sequence on the ZFS layer" in body, (
        "weaver dashboard missing master spec § 21 verbatim quotation"
    )


def test_dashboard_quotes_operator_standing_rule_verbatim():
    body = WEAVER_DASHBOARD_JSON.read_text(encoding="utf-8")
    assert "We do not minimize anything" in body, (
        "weaver dashboard missing §1g verbatim standing rule"
    )


def test_dashboard_listed_in_readme():
    readme = (WEAVER_DASHBOARD_JSON.parent / "README.md").read_text(encoding="utf-8")
    assert "sovereign-os-weaver.json" in readme, (
        "dashboards/README.md missing sovereign-os-weaver.json entry"
    )


def test_dashboard_tagged_sovereign_os():
    data = json.loads(WEAVER_DASHBOARD_JSON.read_text(encoding="utf-8"))
    tags = data.get("tags") or []
    assert "sovereign-os" in tags
    assert "weaver" in tags


def test_weaver_registered_in_surface_map():
    """R496 registers `weaver` as a first-class MODULE_COVERAGE entry —
    dashboard MUST appear as a shipped surface, NOT as a FUTURE waiver."""
    sm_path = REPO_ROOT / "scripts" / "operator" / "surface-map.py"
    result = subprocess.run(
        ["python3", str(sm_path), "coverage", "--module",
         "weaver", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, (
        f"surface-map coverage weaver failed: {result.stderr[:300]}"
    )
    data = json.loads(result.stdout)
    entries = data.get("coverage", [data])
    entry = entries[0] if entries else {}
    surface_count = entry.get("surface_count", 0)
    assert surface_count >= 3, (
        f"weaver must be at >=3 surfaces post-R496; got {surface_count}"
    )
    matrix = entry.get("matrix", [])
    dashboard_row = next(
        (r for r in matrix if r.get("surface") == "dashboard"), None
    )
    assert dashboard_row is not None, (
        "weaver coverage matrix missing 'dashboard' row"
    )
    assert dashboard_row.get("state") == "shipped", (
        f"weaver dashboard surface must be shipped; got {dashboard_row}"
    )
