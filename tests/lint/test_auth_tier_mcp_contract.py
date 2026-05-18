"""R502 (E11.M7++) — auth-tier MCP surface contract lint.

Closes the auth-tier mcp:FUTURE waiver. Raises the auth-tier surface
count from 5 → 6 shipped surfaces (core / cli / dashboard / api /
service / mcp). Second commit in the auth-tier tier-3 surface-expansion
arc.

Per operator §1g verbatim (sacrosanct):

  "We do not minimize anything."

The MCP surface is exposed via the existing R286 aggregator
(scripts/interop/mcp-aggregate.py LOCAL_TOOLS registry) as read-only
tool entries. Each tool delegates to a `sovereign-osctl auth-tier
<verb> --json` invocation. Mutation verb `set` stays CLI-only —
operator §17 sacrosanct sovereignty boundary, matching the read-only
stance the rest of LOCAL_TOOLS takes.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MCP_AGGREGATE = REPO_ROOT / "scripts" / "interop" / "mcp-aggregate.py"


def _manifest() -> dict:
    result = subprocess.run(
        ["python3", str(MCP_AGGREGATE), "manifest", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, (
        f"mcp-aggregate manifest failed: {result.stderr[:300]}"
    )
    return json.loads(result.stdout)


def _tools_by_name(manifest: dict) -> dict:
    return {t["name"]: t for t in manifest.get("tools", [])}


def test_mcp_surface_lists_auth_tier_tools():
    """R502 MCP surface MUST advertise the 4 read-only auth-tier verbs
    (list-tiers / registry / show / matrix)."""
    tools = _tools_by_name(_manifest())
    required = {
        "auth-tier-list-tiers",
        "auth-tier-registry",
        "auth-tier-show",
        "auth-tier-matrix",
    }
    missing = required - set(tools.keys())
    assert not missing, (
        f"MCP manifest missing auth-tier tools: {sorted(missing)}"
    )


def test_mcp_auth_tier_tools_have_operator_g_category():
    """Every R502 auth-tier MCP tool MUST carry the 'operator-§1g'
    category tag so MCP clients can filter on §1g surfaces. Catches
    drift where a future entry is added without the standing-rule tag."""
    tools = _tools_by_name(_manifest())
    for name in ("auth-tier-list-tiers", "auth-tier-registry",
                 "auth-tier-show", "auth-tier-matrix"):
        t = tools[name]
        assert "operator-§1g" in t.get("categories", []), (
            f"MCP tool {name!r} missing 'operator-§1g' category"
        )
        assert "auth-tier" in t.get("categories", []), (
            f"MCP tool {name!r} missing 'auth-tier' category"
        )


def test_mcp_auth_tier_tools_invoke_via_osctl():
    """Each R502 tool MUST invoke `sovereign-osctl auth-tier <verb>
    --json` — that's the load-bearing wire contract."""
    tools = _tools_by_name(_manifest())
    verb_for = {
        "auth-tier-list-tiers": "list-tiers",
        "auth-tier-registry":   "registry",
        "auth-tier-show":       "show",
        "auth-tier-matrix":     "matrix",
    }
    for name, verb in verb_for.items():
        argv = tools[name].get("argv") or []
        assert argv[:2] == ["sovereign-osctl", "auth-tier"], (
            f"MCP tool {name!r} argv must start with sovereign-osctl "
            f"auth-tier; got {argv}"
        )
        assert verb in argv, (
            f"MCP tool {name!r} argv missing verb {verb!r}: {argv}"
        )
        assert "--json" in argv, (
            f"MCP tool {name!r} argv missing --json flag: {argv}"
        )


def test_mcp_auth_tier_tools_are_read_only():
    """Mutation verb `set` MUST NOT appear as an MCP tool — operator
    §17 sacrosanct sovereignty boundary. The MCP aggregator intentionally
    excludes mutating verbs."""
    tools = _tools_by_name(_manifest())
    forbidden = {
        "auth-tier-set",
        "auth-tier-apply",
        "auth-tier-install",
        "auth-tier-mutate",
    }
    leaked = forbidden & set(tools.keys())
    assert not leaked, (
        f"MCP manifest leaks mutation verbs (§17 boundary violation): "
        f"{sorted(leaked)}"
    )


def test_mcp_auth_tier_tools_have_descriptive_summaries():
    """Every R502 auth-tier MCP tool MUST carry a non-empty summary
    that mentions 'auth-tier' so MCP-client tool-pickers see useful
    descriptions, not bare names."""
    tools = _tools_by_name(_manifest())
    for name in ("auth-tier-list-tiers", "auth-tier-registry",
                 "auth-tier-show", "auth-tier-matrix"):
        summary = tools[name].get("summary", "")
        assert summary, f"MCP tool {name!r} has empty summary"
        assert len(summary) >= 30, (
            f"MCP tool {name!r} summary too short ({len(summary)} chars); "
            f"operator-§1g rule: descriptive, not minimized"
        )
        assert "auth-tier" in summary.lower() or \
            "tier" in summary.lower(), (
            f"MCP tool {name!r} summary must mention auth-tier: {summary!r}"
        )


def test_auth_tier_surface_map_extended_to_mcp():
    """R502 extends auth-tier surface-map to 6 shipped surfaces —
    mcp MUST appear as shipped, NOT as a FUTURE waiver."""
    sm_path = REPO_ROOT / "scripts" / "operator" / "surface-map.py"
    result = subprocess.run(
        ["python3", str(sm_path), "coverage", "--module",
         "auth-tier", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, (
        f"surface-map coverage auth-tier failed: {result.stderr[:300]}"
    )
    data = json.loads(result.stdout)
    entries = data.get("coverage", [data])
    entry = entries[0] if entries else {}
    surface_count = entry.get("surface_count", 0)
    assert surface_count >= 6, (
        f"auth-tier must be at >=6 surfaces post-R502; got {surface_count}"
    )
    matrix = entry.get("matrix", [])
    mcp_row = next(
        (r for r in matrix if r.get("surface") == "mcp"), None
    )
    assert mcp_row is not None, (
        "auth-tier coverage matrix missing 'mcp' row"
    )
    assert mcp_row.get("state") == "shipped", (
        f"auth-tier mcp surface must be shipped; got {mcp_row}"
    )
