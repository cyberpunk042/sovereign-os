"""R538 (E5++) — auditor MCP surface contract lint.

Closes the auditor mcp:FUTURE waiver. Raises the auditor surface
count from 5 -> 6 shipped surfaces (core / cli / tui / service /
dashboard / mcp). Second commit in the auditor tier-3 surface-
expansion arc (R537 TUI → R538 MCP → R539 API + webapp).
Mirrors the weaver MCP R535 pattern.

Operator §17 sovereignty boundary: MCP exposes ONLY read-only
inspection — `auditor status` (brief tier panel), `auditor
last-violation` (last security_audit.log entry), and `auditor
history` (bounded tail of security_audit.log). The neutralization
path (Tetragon kernel hook → SIGKILL via guardian-core) stays
CCD-triggered + CLI-gated and is intentionally NOT exposed via
MCP — same pattern as weaver R535 (write/read mutation verbs
stay CLI-only) and surface-map R532 (no `surface-map-waivers`
MCP tool because it takes a runtime arg), and the ceiling-
promotion rule (R510/R515/R518/R521/R524/R527/R530/R533/R536)
that mutation/runtime-arg surfaces stay CLI-gated.

Per operator §1g 8-surface delivery contract anchor verbatim (R453):

  "everything is not just core, not just cli, not just TUI, not
   just API, not just tool and MCP but also Dashboards and Web
   Apps and Services"
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MCP_AGG = REPO_ROOT / "scripts" / "interop" / "mcp-aggregate.py"
SURFACE_MAP = REPO_ROOT / "scripts" / "operator" / "surface-map.py"
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"

# The exact MCP tools R538 lands. The neutralization path stays CLI-
# gated per operator §17. Three read-only verbs mirror the weaver
# R535 (LIVE+STATIC pair) shape, expanded to (status + last-violation
# + history) because the auditor surface has more semantic dimensions
# than weaver's catalog-vs-inventory split.
REQUIRED_TOOLS = {
    "auditor-status",
    "auditor-last-violation",
    "auditor-history",
}


def _load_mcp_aggregate():
    spec = importlib.util.spec_from_file_location("_mcp_agg", MCP_AGG)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_mcp_aggregate_present():
    assert MCP_AGG.is_file()


def test_required_auditor_tools_listed_in_aggregate():
    mod = _load_mcp_aggregate()
    names = {t["name"] for t in mod.LOCAL_TOOLS}
    missing = REQUIRED_TOOLS - names
    assert not missing, (
        f"R538: missing auditor MCP tools: {sorted(missing)}; "
        f"got {sorted(names)}"
    )


def test_auditor_tools_have_fixed_argv_shape():
    """Per R286: MCP aggregator tools MUST have fixed argv (no
    runtime args)."""
    mod = _load_mcp_aggregate()
    for tool in mod.LOCAL_TOOLS:
        if tool["name"] not in REQUIRED_TOOLS:
            continue
        argv = tool["argv"]
        assert argv[0] == "sovereign-osctl"
        assert argv[1] == "auditor"
        assert argv[-1] == "--json", (
            f"{tool['name']} must terminate with --json so the MCP "
            f"client gets structured data; got {argv}"
        )
        for arg in argv:
            assert "<" not in arg and ">" not in arg, (
                f"{tool['name']} argv has runtime-arg slot {arg!r} — "
                f"MCP tools have fixed argv only (per R286)"
            )


def test_auditor_tools_are_read_only_verbs_only():
    """Operator §17 sovereignty: ONLY read-only inspection verbs
    (`status`, `last-violation`, `history`) are exposed via MCP.
    Neutralization (Tetragon → SIGKILL via guardian-core) stays
    CCD-triggered + CLI-gated and MUST NOT have an MCP entry.

    We assert positively: every auditor MCP tool's third argv slot
    (the verb) must be in the read-only allowlist. Any new mutation/
    neutralization verb (e.g. `auditor neutralize`, `auditor kill`,
    `auditor purge`) would automatically violate."""
    mod = _load_mcp_aggregate()
    auditor_argvs = [
        t["argv"] for t in mod.LOCAL_TOOLS
        if len(t["argv"]) >= 2 and t["argv"][1] == "auditor"
    ]
    read_only_allowlist = {"status", "last-violation", "history",
                           "full"}
    for argv in auditor_argvs:
        verb = argv[2] if len(argv) > 2 else ""
        assert verb in read_only_allowlist, (
            f"R538: MCP must only expose read-only auditor verbs "
            f"(operator §17 sovereignty boundary); got verb "
            f"{verb!r} in argv = {argv}"
        )


def test_auditor_tools_have_descriptive_summaries():
    """Each tool summary MUST be substantive (>=30 chars), mention
    'auditor' or 'audit log' / 'guardian' / 'tetragon', and surface
    the master spec anchor — operator-§1g UX rule: 30-second readable."""
    mod = _load_mcp_aggregate()
    for tool in mod.LOCAL_TOOLS:
        if tool["name"] not in REQUIRED_TOOLS:
            continue
        summary = tool.get("summary", "")
        assert len(summary) >= 30, (
            f"{tool['name']} summary too thin: {summary!r}"
        )
        low = summary.lower()
        assert (
            "auditor" in low or "audit" in low
            or "guardian" in low or "tetragon" in low
        ), (
            f"{tool['name']} summary must reference auditor / audit / "
            f"guardian / tetragon: {summary!r}"
        )
        assert "master spec" in low or "§" in summary, (
            f"{tool['name']} summary must reference the master spec "
            f"anchor: {summary!r}"
        )


def test_auditor_tools_summary_surfaces_sovereignty_boundary():
    """Operator-§17 sovereignty boundary MUST surface in the auditor
    tool summaries — agents reading the MCP manifest must learn that
    neutralization stays CLI-gated. Mirrors the weaver R535 pattern
    (state-fabric writes stay CLI-only)."""
    mod = _load_mcp_aggregate()
    for tool in mod.LOCAL_TOOLS:
        if tool["name"] not in REQUIRED_TOOLS:
            continue
        summary = tool.get("summary", "")
        low = summary.lower()
        assert (
            "§17" in summary or "section 17" in low
            or "sovereignty" in low
            or "read-only" in low or "cli-gated" in low
            or "cli-only" in low
        ), (
            f"{tool['name']} summary must reference §17 / sovereignty "
            f"/ read-only / cli-gated; got: {summary!r}"
        )


def test_auditor_tools_invoke_actual_osctl_verbs():
    """End-to-end smoke: the argv each MCP tool emits MUST produce
    JSON-parseable output when run (so the MCP client gets a usable
    payload). DRY_RUN-safe — these are read-only inspection verbs."""
    mod = _load_mcp_aggregate()
    for tool in mod.LOCAL_TOOLS:
        if tool["name"] not in REQUIRED_TOOLS:
            continue
        argv = list(tool["argv"])
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
        assert isinstance(payload, dict), (
            f"{tool['name']} JSON payload must be a dict; got "
            f"{type(payload).__name__}"
        )


def test_auditor_status_json_shape():
    """`auditor status --json` MUST emit the trinity-inspect auditor
    payload — tier=auditor, spec_ref, always_on, tetragon_available,
    service shape."""
    cp = subprocess.run(
        ["bash", str(OSCTL), "auditor", "status", "--json"],
        capture_output=True, text=True, timeout=15,
        env={"PATH": "/usr/bin:/bin", "HOME": "/tmp"},
    )
    assert cp.returncode == 0, cp.stderr[:300]
    payload = json.loads(cp.stdout)
    assert payload.get("tier") == "auditor"
    assert payload.get("always_on") is True
    assert "tetragon_available" in payload
    assert "service" in payload
    assert payload["service"].get("name") == "sovereign-auditor"


def test_auditor_last_violation_json_shape():
    """`auditor last-violation --json` MUST emit the operator-named
    shape: module, verb, spec_ref, log_path, present, sovereignty_
    boundary, line."""
    cp = subprocess.run(
        ["bash", str(OSCTL), "auditor", "last-violation", "--json"],
        capture_output=True, text=True, timeout=15,
        env={"PATH": "/usr/bin:/bin", "HOME": "/tmp"},
    )
    assert cp.returncode == 0, cp.stderr[:300]
    payload = json.loads(cp.stdout)
    assert payload.get("module") == "auditor"
    assert payload.get("verb") == "last-violation"
    assert "spec_ref" in payload
    assert "§ 10" in payload["spec_ref"]
    assert "log_path" in payload
    assert "security_audit.log" in payload["log_path"]
    assert "present" in payload
    assert "sovereignty_boundary" in payload
    assert "§17" in payload["sovereignty_boundary"] \
        or "section 17" in payload["sovereignty_boundary"].lower()


def test_auditor_history_json_shape():
    """`auditor history --json` MUST emit module, verb, log_path,
    present, requested_n, sovereignty_boundary, count, lines[]."""
    cp = subprocess.run(
        ["bash", str(OSCTL), "auditor", "history", "--json"],
        capture_output=True, text=True, timeout=15,
        env={"PATH": "/usr/bin:/bin", "HOME": "/tmp"},
    )
    assert cp.returncode == 0, cp.stderr[:300]
    payload = json.loads(cp.stdout)
    assert payload.get("module") == "auditor"
    assert payload.get("verb") == "history"
    assert payload.get("requested_n") == 20
    assert isinstance(payload.get("lines"), list)
    assert "count" in payload
    assert "present" in payload


def test_auditor_extended_to_mcp_surface():
    """R538 extends the auditor entry to >=6 shipped surfaces — mcp
    MUST appear as shipped, NOT as a FUTURE waiver."""
    result = subprocess.run(
        ["python3", str(SURFACE_MAP), "coverage", "--module",
         "auditor", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr[:300]
    data = json.loads(result.stdout)
    entries = data.get("coverage", [data])
    entry = entries[0] if entries else {}
    assert entry.get("surface_count", 0) >= 6, (
        f"auditor must be at >=6 surfaces post-R538; got {entry}"
    )
    matrix = entry.get("matrix", [])
    mcp_row = next(
        (r for r in matrix if r.get("surface") == "mcp"), None
    )
    assert mcp_row is not None, "auditor matrix missing mcp row"
    assert mcp_row.get("state") == "shipped", (
        f"auditor mcp surface must be shipped post-R538; got {mcp_row}"
    )
    # R538 drains the mcp waiver. R539 will drain api + webapp. The
    # auditor service ALREADY ships (R155 guardian-core daemon) so
    # only 2 FUTURE waivers should remain post-R538.
    future_count = entry.get("future_waiver_count", 0)
    assert future_count <= 2, (
        f"auditor must have at most 2 FUTURE waivers remaining post-"
        f"R538 (api/webapp); got {future_count}"
    )
