"""R535 (E5++) — weaver MCP surface contract lint.

Closes the weaver mcp:FUTURE waiver. Raises the weaver surface count
from 4 -> 5 shipped surfaces (core / cli / tui / dashboard / mcp).
Second commit in the weaver tier-3 surface-expansion arc (R534 TUI →
R535 MCP → R536 API + webapp + service). Mirrors the surface-map
R532 / ux-design-audit R529 / doc-coverage R526 / anti-min R523 /
compliance R520 / router R517 MCP-tool patterns.

Operator §17 sovereignty boundary: MCP exposes ONLY read-only
inspection — `weaver list` (LIVE state-fabric presence + size +
mtime) and `weaver state-files` (STATIC master spec § 7.1 catalog).
The mutation verbs `weaver write` (atomic-state write) and
`weaver read` (per-file read with runtime arg) are intentionally
NOT exposed via MCP: state-fabric writes are sovereignty-critical
and stay manual + CLI-gated. This is consistent with the surface-
map R532 pattern (no `surface-map-waivers` MCP tool because it
takes a runtime arg) and the ceiling-promotion rule (R510/R515/
R518/R521/R524/R527/R530/R533) that mutation surfaces stay CLI-
gated.

Per operator §1g 8-surface delivery contract anchor verbatim (R453):

  "everything is not just core, not just cli, not just TUI, not just
   API, not just tool and MCP but also Dashboards and Web Apps and
   Services"
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MCP_AGG = REPO_ROOT / "scripts" / "interop" / "mcp-aggregate.py"
SURFACE_MAP = REPO_ROOT / "scripts" / "operator" / "surface-map.py"
ATOMIC_STATE = REPO_ROOT / "scripts" / "weaver" / "atomic-state.py"
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"

# The exact MCP tools R535 lands. The mutation verbs (read / write)
# stay CLI-gated per operator §17. The LIVE+STATIC pair mirrors the
# R532 surface-map shape (surfaces=catalog + coverage=live).
REQUIRED_TOOLS = {"weaver-list", "weaver-state-files"}


def _load_mcp_aggregate():
    spec = importlib.util.spec_from_file_location("_mcp_agg", MCP_AGG)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_mcp_aggregate_present():
    assert MCP_AGG.is_file()


def test_required_weaver_tools_listed_in_aggregate():
    mod = _load_mcp_aggregate()
    names = {t["name"] for t in mod.LOCAL_TOOLS}
    missing = REQUIRED_TOOLS - names
    assert not missing, (
        f"R535: missing weaver MCP tools: {sorted(missing)}; "
        f"got {sorted(names)}"
    )


def test_weaver_tools_have_fixed_argv_shape():
    """Per R286: MCP aggregator tools MUST have fixed argv (no
    runtime args)."""
    mod = _load_mcp_aggregate()
    for tool in mod.LOCAL_TOOLS:
        if tool["name"] not in REQUIRED_TOOLS:
            continue
        argv = tool["argv"]
        assert argv[0] == "sovereign-osctl"
        assert argv[1] == "weaver"
        assert argv[-1] == "--json", (
            f"{tool['name']} must terminate with --json so the MCP "
            f"client gets structured data; got {argv}"
        )
        # All arg slots must be literal — runtime args are not allowed
        # in MCP tools.
        for arg in argv:
            assert "<" not in arg and ">" not in arg, (
                f"{tool['name']} argv has runtime-arg slot {arg!r} — "
                f"MCP tools have fixed argv only (per R286)"
            )


def test_weaver_tools_are_read_only_verbs_only():
    """Operator §17 sovereignty: ONLY read-only verbs (`list`,
    `state-files`) are exposed via MCP. `write` (atomic-state mutation)
    and `read` (per-file with runtime arg) MUST NOT have MCP entries."""
    mod = _load_mcp_aggregate()
    weaver_argvs = [
        t["argv"] for t in mod.LOCAL_TOOLS
        if len(t["argv"]) >= 2 and t["argv"][1] == "weaver"
    ]
    forbidden_verbs = {"write", "read"}
    for argv in weaver_argvs:
        verb = argv[2] if len(argv) > 2 else ""
        assert verb not in forbidden_verbs, (
            f"R535: MCP must not expose mutation/runtime-arg weaver "
            f"verb {verb!r} (operator §17 sovereignty boundary); "
            f"argv = {argv}"
        )


def test_weaver_tools_have_descriptive_summaries():
    """Each tool summary MUST be substantive (>=30 chars), mention
    'weaver' or 'state-fabric', and surface the master spec anchor —
    operator-§1g UX rule: 30-second readable."""
    mod = _load_mcp_aggregate()
    for tool in mod.LOCAL_TOOLS:
        if tool["name"] not in REQUIRED_TOOLS:
            continue
        summary = tool.get("summary", "")
        assert len(summary) >= 30, (
            f"{tool['name']} summary too thin: {summary!r}"
        )
        low = summary.lower()
        assert ("weaver" in low or "state-fabric" in low), (
            f"{tool['name']} summary must reference weaver / state-"
            f"fabric: {summary!r}"
        )
        # Master spec anchor must surface — operator-§1g 30-second
        # readable rule.
        assert "master spec" in low or "§" in summary, (
            f"{tool['name']} summary must reference the master spec "
            f"anchor: {summary!r}"
        )


def test_weaver_tools_invoke_actual_osctl_verbs():
    """End-to-end smoke: the argv each MCP tool emits MUST produce
    JSON-parseable output when run (so the MCP client gets a usable
    payload). DRY_RUN-safe — these are read-only inspection verbs."""
    mod = _load_mcp_aggregate()
    for tool in mod.LOCAL_TOOLS:
        if tool["name"] not in REQUIRED_TOOLS:
            continue
        argv = list(tool["argv"])
        # Substitute the actual repo paths so we don't depend on PATH.
        if argv[0] == "sovereign-osctl":
            argv[0] = str(OSCTL)
            argv.insert(0, "bash")
        result = subprocess.run(
            argv, capture_output=True, text=True, timeout=15,
            env={"PATH": "/usr/bin:/bin", "HOME": "/tmp"},
        )
        assert result.returncode == 0, (
            f"{tool['name']} ({tool['argv']}) failed: "
            f"{result.stderr[:300]}"
        )
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            raise AssertionError(
                f"{tool['name']} stdout is not JSON: {e}; "
                f"head: {result.stdout[:200]!r}"
            )
        # Both tools must report the count + files shape.
        assert "count" in payload or "files" in payload, (
            f"{tool['name']} JSON missing count/files: {payload!r}"
        )


def test_weaver_list_live_payload_shape():
    """`weaver list --json` MUST emit the LIVE 4-state-fabric file
    inventory with present + size + mtime per row."""
    cp = subprocess.run(
        ["bash", str(OSCTL), "weaver", "list", "--json"],
        capture_output=True, text=True, timeout=15,
        env={"PATH": "/usr/bin:/bin", "HOME": "/tmp"},
    )
    assert cp.returncode == 0, cp.stderr[:300]
    payload = json.loads(cp.stdout)
    assert "context_dir" in payload
    assert payload.get("count") == 4
    names = {r["name"] for r in payload["files"]}
    assert names == {"IDENTITY.md", "SOUL.md", "AGENTS.md", "CLAUDE.md"}
    for row in payload["files"]:
        assert "present" in row
        # Absent rows must still carry the keys (null-shaped).
        assert "size_bytes" in row
        assert "mtime_epoch" in row


def test_weaver_state_files_catalog_shape():
    """`weaver state-files --json` MUST emit the master spec § 7.1
    static 4-state catalog independent of whether files exist."""
    cp = subprocess.run(
        ["bash", str(OSCTL), "weaver", "state-files", "--json"],
        capture_output=True, text=True, timeout=15,
        env={"PATH": "/usr/bin:/bin", "HOME": "/tmp"},
    )
    assert cp.returncode == 0, cp.stderr[:300]
    payload = json.loads(cp.stdout)
    assert payload.get("count") == 4
    assert "master spec" in payload.get("spec_anchor", "").lower()
    ids = {r["id"] for r in payload["files"]}
    assert ids == {"IDENTITY.md", "SOUL.md", "AGENTS.md", "CLAUDE.md"}
    for row in payload["files"]:
        assert "id" in row
        assert "label" in row
        assert "master_spec_ref" in row
        assert "operator_named" in row


def test_weaver_extended_to_mcp_surface():
    """R535 extends the weaver entry to 5 shipped surfaces — mcp MUST
    appear as shipped, NOT as a FUTURE waiver."""
    result = subprocess.run(
        ["python3", str(SURFACE_MAP), "coverage", "--module",
         "weaver", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr[:300]
    data = json.loads(result.stdout)
    entries = data.get("coverage", [data])
    entry = entries[0] if entries else {}
    assert entry.get("surface_count", 0) >= 5, (
        f"weaver must be at >=5 surfaces post-R535; got {entry}"
    )
    matrix = entry.get("matrix", [])
    mcp_row = next(
        (r for r in matrix if r.get("surface") == "mcp"), None
    )
    assert mcp_row is not None, "weaver matrix missing mcp row"
    assert mcp_row.get("state") == "shipped", (
        f"weaver mcp surface must be shipped post-R535; got {mcp_row}"
    )
    # R535 drains the mcp waiver. R536 will drain api + webapp (and
    # may REPLACE the service: not applicable waiver with a real
    # read-only daemon, same ceiling-promotion pattern as R510/R515/
    # R518/R521/R524/R527/R530/R533).
    future_count = entry.get("future_waiver_count", 0)
    assert future_count == 2, (
        f"weaver must have exactly 2 FUTURE waivers remaining post-"
        f"R535 (api/webapp); got {future_count}"
    )


def test_atomic_state_supports_json_for_list_and_catalog():
    """The atomic-state primitive MUST natively support --json on
    both `list` and `state-files` subcommands — the osctl delegation
    just passes args through, so the primitive is load-bearing."""
    cp = subprocess.run(
        ["python3", str(ATOMIC_STATE), "list", "--json"],
        capture_output=True, text=True, timeout=10,
    )
    assert cp.returncode == 0, cp.stderr[:300]
    json.loads(cp.stdout)  # raises on parse failure
    cp = subprocess.run(
        ["python3", str(ATOMIC_STATE), "state-files", "--json"],
        capture_output=True, text=True, timeout=10,
    )
    assert cp.returncode == 0, cp.stderr[:300]
    json.loads(cp.stdout)
