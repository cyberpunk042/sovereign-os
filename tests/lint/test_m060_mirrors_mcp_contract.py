"""M060 cross-repo mirror MCP surface contract — closes the mcp:FUTURE
waiver for the 8 selfdef→sovereign-os mirror domains.

Closes the M060 cross-repo mirror MCP gap. Raises each mirror's surface
count by adding the mcp surface (already had core / cli / api / webapp /
service via the prior arcs).

Per operator §1g verbatim (sacrosanct):

  "We do not minimize anything."

The MCP surface is exposed via the existing R286 aggregator
(scripts/interop/mcp-aggregate.py LOCAL_TOOLS registry) as read-only
tool entries. Each tool delegates to a `sovereign-osctl <slug> <verb>
--json` invocation. NONE of the 7 mirrors expose a mutation verb at the
MCP surface — operator §17 sacrosanct sovereignty boundary; all
mutations (grant issue, capability revoke, sandbox release, audit
verify, quarantine release, trust-score reset) are selfdefctl + MS003
verbs on the selfdef IPS side only (MS043 R10212).

Per "Respect the projects": MCP clients (Claude, local models with
MCP-aware runners) can query selfdef state through these read-only
mirror tools without touching the selfdef daemon directly.
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


# 8 mirror domains (one tool per snapshot verb) + 1 D-16 integrity tool
# + 1 D-12 summaries tool + 2 MS007 TUI-mirror tools (snapshot + panels).
REQUIRED_TOOLS = {
    "selfdef-profile-mirror-show",
    "selfdef-rules-mirror-snapshot",
    "selfdef-rules-mirror-summaries",
    "selfdef-grants-mirror-snapshot",
    "selfdef-capability-mirror-snapshot",
    "selfdef-sandbox-mirror-snapshot",
    "selfdef-audit-mirror-snapshot",
    "selfdef-audit-mirror-integrity",
    "selfdef-quarantine-mirror-snapshot",
    "selfdef-trust-mirror-snapshot",
    "selfdef-tui-mirror-snapshot",
    "selfdef-tui-mirror-panels",
    "selfdef-cli-mirror-snapshot",
    "selfdef-cli-mirror-summaries",
    "selfdef-cli-mirror-mutating",
}

# Each tool delegates to a specific sovereign-osctl mirror-slug + verb.
EXPECTED_ARGV = {
    "selfdef-profile-mirror-show":
        ["sovereign-osctl", "profile-mirror", "show", "--json"],
    "selfdef-rules-mirror-snapshot":
        ["sovereign-osctl", "rules-mirror", "snapshot", "--json"],
    "selfdef-rules-mirror-summaries":
        ["sovereign-osctl", "rules-mirror", "summaries", "--json"],
    "selfdef-grants-mirror-snapshot":
        ["sovereign-osctl", "grants-mirror", "snapshot", "--json"],
    "selfdef-capability-mirror-snapshot":
        ["sovereign-osctl", "capability-mirror", "snapshot", "--json"],
    "selfdef-sandbox-mirror-snapshot":
        ["sovereign-osctl", "sandbox-mirror", "snapshot", "--json"],
    "selfdef-audit-mirror-snapshot":
        ["sovereign-osctl", "audit-mirror", "snapshot", "--json"],
    "selfdef-audit-mirror-integrity":
        ["sovereign-osctl", "audit-mirror", "integrity", "--json"],
    "selfdef-quarantine-mirror-snapshot":
        ["sovereign-osctl", "quarantine-mirror", "snapshot", "--json"],
    "selfdef-trust-mirror-snapshot":
        ["sovereign-osctl", "trust-mirror", "snapshot", "--json"],
    "selfdef-tui-mirror-snapshot":
        ["sovereign-osctl", "tui-mirror", "snapshot", "--json"],
    "selfdef-tui-mirror-panels":
        ["sovereign-osctl", "tui-mirror", "panels", "--json"],
    "selfdef-cli-mirror-snapshot":
        ["sovereign-osctl", "cli-mirror", "snapshot", "--json"],
    "selfdef-cli-mirror-summaries":
        ["sovereign-osctl", "cli-mirror", "summaries", "--json"],
    "selfdef-cli-mirror-mutating":
        ["sovereign-osctl", "cli-mirror", "mutating", "--json"],
}


def test_mcp_surface_lists_all_eight_m060_mirror_tools():
    """All 8 M060 mirror snapshot tools + D-16 integrity + D-12 summaries
    MUST appear in the MCP manifest — operator §1g rule: full ladder
    visible."""
    tools = _tools_by_name(_manifest())
    missing = REQUIRED_TOOLS - set(tools.keys())
    assert not missing, (
        f"MCP manifest missing M060 mirror tools: {sorted(missing)}"
    )


def test_mcp_m060_mirror_tools_have_required_categories():
    """Each M060 mirror MCP tool MUST carry the 'operator-§1g' + 'm060' +
    'selfdef-mirror' tags. The 8 D-NN-tied mirrors additionally carry a
    'd-NN' per-dashboard tag; cross-cutting MS007 mirrors (tui-layout,
    cli-mirror) carry an 'ms007' tag instead."""
    tools = _tools_by_name(_manifest())
    for name in REQUIRED_TOOLS:
        cats = tools[name].get("categories", [])
        assert "operator-§1g" in cats, (
            f"MCP tool {name!r} missing 'operator-§1g' category"
        )
        assert "m060" in cats, (
            f"MCP tool {name!r} missing 'm060' category"
        )
        assert "selfdef-mirror" in cats, (
            f"MCP tool {name!r} missing 'selfdef-mirror' category"
        )
        d_tags = [c for c in cats if c.startswith("d-")]
        if d_tags:
            continue  # D-NN-tied mirror (D-02/12/13/14/15/16/17/18)
        # Cross-cutting MS007 mirrors must carry the 'ms007' tag.
        assert "ms007" in cats, (
            f"MCP tool {name!r} missing both 'd-NN' and 'ms007' tag: {cats}"
        )


def test_mcp_m060_mirror_tools_invoke_via_osctl():
    """Each tool MUST invoke `sovereign-osctl <mirror-slug> <verb>
    --json` — that's the load-bearing wire contract."""
    tools = _tools_by_name(_manifest())
    for name, expected in EXPECTED_ARGV.items():
        argv = tools[name].get("argv") or []
        assert argv == expected, (
            f"MCP tool {name!r} argv mismatch:\n"
            f"  expected: {expected}\n"
            f"  got:      {argv}"
        )


def test_mcp_m060_mirror_tools_are_read_only():
    """None of the 7 mirror domains expose a mutation verb at MCP —
    operator §17 sacrosanct sovereignty boundary; ALL mutations
    (grant issue, capability revoke, sandbox release, audit verify,
    quarantine release, trust-score reset) are selfdefctl + MS003
    on the selfdef IPS side only (MS043 R10212)."""
    tools = _tools_by_name(_manifest())
    forbidden = {
        # grant lifecycle
        "selfdef-grants-mirror-issue",
        "selfdef-grants-mirror-revoke",
        # capability lifecycle
        "selfdef-capability-mirror-issue",
        "selfdef-capability-mirror-revoke",
        # sandbox lifecycle
        "selfdef-sandbox-mirror-allocate",
        "selfdef-sandbox-mirror-release",
        "selfdef-sandbox-mirror-checkpoint",
        # audit chain — APPEND-ONLY by MS016 R03567 (no append surface
        # is ever exposed to operators; daemon-only append)
        "selfdef-audit-mirror-append",
        "selfdef-audit-mirror-replay",
        "selfdef-audit-mirror-edit",
        # quarantine override
        "selfdef-quarantine-mirror-release",
        "selfdef-quarantine-mirror-forfeit",
        # trust-score override
        "selfdef-trust-mirror-reset",
        "selfdef-trust-mirror-admit",
        # profile lifecycle
        "selfdef-profile-mirror-set",
        "selfdef-profile-mirror-switch",
        # nft rule lifecycle (rules are installed via selfdefctl + nft
        # at the IPS layer — never via the read-only mirror)
        "selfdef-rules-mirror-add",
        "selfdef-rules-mirror-delete",
        "selfdef-rules-mirror-flush",
    }
    leaked = forbidden & set(tools.keys())
    assert not leaked, (
        f"MCP manifest leaks mutation verbs (§17 + R10212 boundary "
        f"violation — IPS mutations must be selfdefctl + MS003 only): "
        f"{sorted(leaked)}"
    )


def test_mcp_m060_mirror_tools_have_descriptive_summaries():
    """Every M060 mirror MCP tool MUST carry a non-empty summary that
    mentions its M060 dashboard id (D-NN) + the selfdef milestone
    backing it (MSxxx) so MCP-client tool-pickers see useful
    descriptions — operator-§1g rule: descriptive, not minimized."""
    tools = _tools_by_name(_manifest())
    for name in REQUIRED_TOOLS:
        summary = tools[name].get("summary", "")
        assert summary, f"MCP tool {name!r} has empty summary"
        assert len(summary) >= 80, (
            f"MCP tool {name!r} summary too short ({len(summary)} "
            f"chars); operator-§1g rule: descriptive, not minimized"
        )
        # Every D-NN-tied M060 mirror tool should reference its D-NN id;
        # cross-cutting MS007 mirrors are exempt (the tui-layout schema
        # spans all 4 panels and isn't tied to a single dashboard slot).
        cats = tools[name].get("categories", [])
        if not any(c.startswith("d-") for c in cats):
            assert "ms007" in cats, (
                f"MCP tool {name!r} lacks D-NN reference but also "
                f"missing 'ms007' tag: {cats}"
            )
        else:
            assert "D-" in summary, (
                f"MCP tool {name!r} summary must reference its D-NN id: "
                f"{summary!r}"
            )
        # Every tool should reference the selfdef MS-rooted milestone
        # that backs it (MS016 / MS032 / MS035 / MS036 / MS037 / MS039 /
        # MS040 / MS042 / MS049 / etc.)
        assert "MS0" in summary or "selfdef" in summary.lower(), (
            f"MCP tool {name!r} summary must reference its selfdef MS "
            f"backing: {summary!r}"
        )


def test_mcp_m060_mirror_tools_carry_d16_integrity_pair():
    """D-16 audit-chain is special: it ships TWO MCP tools (snapshot +
    integrity), since chain integrity is a first-class concern for an
    append-only log and consumers may want to poll integrity cheaply
    without paginating spans."""
    tools = _tools_by_name(_manifest())
    snap = tools["selfdef-audit-mirror-snapshot"]
    integ = tools["selfdef-audit-mirror-integrity"]
    # snapshot tool's summary must mention chain SHA-256 + APPEND-ONLY
    assert "SHA-256" in snap["summary"] or "sha-256" in snap["summary"].lower()
    assert "APPEND-ONLY" in snap["summary"] or "append-only" in snap["summary"].lower()
    # integrity tool's summary must spell out the bare-integrity shape
    assert "integrity" in integ["summary"].lower()
    assert "polling" in integ["summary"].lower() or "head_hash" in integ["summary"]
    # different verbs must land at different osctl sub-verbs
    assert snap["argv"][-2] == "snapshot"
    assert integ["argv"][-2] == "integrity"


def test_mcp_m060_mirror_tools_carry_d12_summaries_pair():
    """D-12 rules-mirror also ships TWO MCP tools (snapshot + summaries),
    since per-ring summary tiles are a first-class cheap-poll surface
    for the Ring 0..4 trust-topology view — consumers may want the
    summary tiles without paginating the full rule list."""
    tools = _tools_by_name(_manifest())
    snap = tools["selfdef-rules-mirror-snapshot"]
    summ = tools["selfdef-rules-mirror-summaries"]
    # snapshot must reference the per-ring trust topology
    assert "Ring 0..4" in snap["summary"] or "ring 0..4" in snap["summary"].lower()
    assert "MS024" in snap["summary"] or "MS038" in snap["summary"] or "MS039" in snap["summary"]
    # summaries must spell out the bare-summary shape
    assert "summary" in summ["summary"].lower() or "summaries" in summ["summary"].lower()
    assert "ring" in summ["summary"].lower()
    # different verbs must land at different osctl sub-verbs
    assert snap["argv"][-2] == "snapshot"
    assert summ["argv"][-2] == "summaries"
