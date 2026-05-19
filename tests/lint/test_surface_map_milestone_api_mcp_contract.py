"""R541 (E5++) — surface-map `milestone` rollup over MCP + REST API.

Extends the R540 first-class `surface-map milestone` rollup verb out
to the §1g 8-surface ladder it itself measures:

  - MCP tool entry `surface-map-milestone` in mcp-aggregate.py (R286
    fixed-argv shape: `sovereign-osctl surface-map milestone --json`).
  - /milestone HTTP endpoint on the surface-map-api daemon, reusing
    `surface-map.py`'s `milestone_rollup()` via importlib (no drift
    between CLI / TUI / MCP / API surfaces).

The rollup is the first-class operator-§1g observable of the R539
historic ceiling-closure milestone: ALL twelve §1g-named modules at
the 8-surface structural ceiling, ZERO FUTURE waivers anywhere.

Per operator §1g verbatim (sacrosanct):

  "We do not minimize anything."

Per operator §1g 8-surface delivery contract (verbatim, R453 anchor):

  "everything is not just core, not just cli, not just TUI, not just
   API, not just tool and MCP but also Dashboards and Web Apps and
   Services"

Sovereignty boundaries enforced by this contract:
  - read-only at every HTTP method except GET/HEAD (operator §17)
  - the rollup is a DERIVED view; no mutation routes (the audited
    modules carry their own remediation surfaces — surface-map does
    not orchestrate remediation, it observes it)
  - MCP argv is fixed (R286) — no runtime-arg slots
"""
from __future__ import annotations

import importlib.util
import json
import os
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
API_PY = REPO_ROOT / "scripts" / "operator" / "surface-map-api.py"
MCP_AGG = REPO_ROOT / "scripts" / "interop" / "mcp-aggregate.py"
SURFACE_MAP = REPO_ROOT / "scripts" / "operator" / "surface-map.py"
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"

TOOL_NAME = "surface-map-milestone"

# Operator §1g 8-surface delivery contract anchor (R453, verbatim).
R453_STANDING_RULE = (
    "everything is not just core, not just cli, not just TUI, not "
    "just API, not just tool and MCP but also Dashboards and Web "
    "Apps and Services."
)

# R540 milestone payload — the 15 required top-level keys. Cross-
# referenced with test_surface_map_milestone_contract.py.
REQUIRED_KEYS = {
    "module", "verb", "spec_ref",
    "total_modules", "at_structural_ceiling_count",
    "full_8_surface_count", "future_carrying_count",
    "at_full_8_surfaces", "at_ceiling_below_8_surfaces",
    "future_carrying_modules",
    "all_at_structural_ceiling", "all_g1g_named_at_full_8",
    "zero_future_waivers",
    "historic_anchor", "standing_rule",
}


def _load_mcp_aggregate():
    spec = importlib.util.spec_from_file_location("_mcp_agg", MCP_AGG)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------- MCP

def test_mcp_tool_registered():
    mod = _load_mcp_aggregate()
    names = {t["name"] for t in mod.LOCAL_TOOLS}
    assert TOOL_NAME in names, (
        f"R541: MCP aggregator must register {TOOL_NAME!r}; "
        f"got {sorted(names)}"
    )


def test_mcp_tool_has_fixed_argv_shape():
    """Per R286: MCP aggregator tools MUST have fixed argv (no runtime
    args). The milestone verb is parameterless so this is a clean fit
    (unlike `surface-map waivers --module <m>` which is intentionally
    NOT exposed via MCP per the R532 ceiling-promotion rule)."""
    mod = _load_mcp_aggregate()
    tool = next(t for t in mod.LOCAL_TOOLS if t["name"] == TOOL_NAME)
    argv = tool["argv"]
    assert argv[0] == "sovereign-osctl"
    assert argv[1] == "surface-map"
    assert argv[2] == "milestone"
    assert argv[-1] == "--json", (
        f"{TOOL_NAME} must terminate with --json (R286 fixed argv); "
        f"got {argv}"
    )
    for arg in argv:
        assert "<" not in arg and ">" not in arg, (
            f"{TOOL_NAME} argv has runtime-arg slot {arg!r} — "
            f"MCP tools have fixed argv only (per R286)"
        )


def test_mcp_tool_summary_is_substantive():
    """Operator-§1g UX rule: 30-second readable rollup. The summary
    MUST mention surface-map, milestone, the §1g contract, and the
    R453 anchor."""
    mod = _load_mcp_aggregate()
    tool = next(t for t in mod.LOCAL_TOOLS if t["name"] == TOOL_NAME)
    summary = tool.get("summary", "")
    assert len(summary) >= 60, (
        f"{TOOL_NAME} summary too thin: {summary!r}"
    )
    low = summary.lower()
    assert "surface-map" in low
    assert "milestone" in low
    assert "§1g" in summary or "g1g" in low or "1g" in summary
    assert "r453" in low, (
        f"{TOOL_NAME} summary must reference the R453 anchor; "
        f"got {summary!r}"
    )
    # Read-only / no-mutation framing must be explicit.
    assert (
        "read-only" in low or "no mutation" in low
        or "no mutation routes" in low or "derived view" in low
    ), (
        f"{TOOL_NAME} summary must surface the read-only framing; "
        f"got {summary!r}"
    )


def test_mcp_tool_categories_include_milestone_and_ceiling():
    mod = _load_mcp_aggregate()
    tool = next(t for t in mod.LOCAL_TOOLS if t["name"] == TOOL_NAME)
    cats = set(tool.get("categories", []))
    assert "milestone" in cats
    assert "surface-map" in cats
    # The operator-§1g category links to the §1g delivery contract.
    assert any(c.startswith("operator-") for c in cats), (
        f"{TOOL_NAME} categories must carry an operator-§ namespace; "
        f"got {sorted(cats)}"
    )


def test_mcp_tool_end_to_end_smoke():
    """End-to-end smoke: the argv the MCP tool emits MUST produce
    JSON-parseable output matching the R540 rollup shape when run."""
    mod = _load_mcp_aggregate()
    tool = next(t for t in mod.LOCAL_TOOLS if t["name"] == TOOL_NAME)
    argv = list(tool["argv"])
    if argv[0] == "sovereign-osctl":
        argv[0] = str(OSCTL)
        argv.insert(0, "bash")
    result = subprocess.run(
        argv, capture_output=True, text=True, timeout=20,
        env={"PATH": "/usr/bin:/bin", "HOME": "/tmp"},
    )
    assert result.returncode == 0, (
        f"{TOOL_NAME} ({tool['argv']}) failed: {result.stderr[:300]}"
    )
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict)
    missing = REQUIRED_KEYS - set(payload.keys())
    assert not missing, (
        f"{TOOL_NAME} rollup missing required R540 keys: "
        f"{sorted(missing)}"
    )
    # R539 invariants — milestone payload MUST report the historic
    # ceiling-closure state.
    assert payload["all_at_structural_ceiling"] is True
    assert payload["zero_future_waivers"] is True
    assert payload["future_carrying_count"] == 0
    assert payload["future_carrying_modules"] == []
    assert payload["full_8_surface_count"] >= 12
    assert "R539" in payload["historic_anchor"]
    assert payload["standing_rule"] == R453_STANDING_RULE


# ---------------------------------------------------- live API daemon

class _DaemonHarness:
    def __init__(self):
        self.port = None
        self.proc = None

    def __enter__(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            self.port = s.getsockname()[1]
        env = os.environ.copy()
        env["SURFACE_MAP_API_BIND"] = "127.0.0.1"
        env["SURFACE_MAP_API_PORT"] = str(self.port)
        env["SOVEREIGN_OS_METRICS_DIR"] = "/tmp/r541-metrics-test"
        self.proc = subprocess.Popen(
            ["python3", str(API_PY)],
            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        deadline = time.time() + 6.0
        last_err = None
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{self.port}/healthz", timeout=1,
                ) as r:
                    if r.status == 200:
                        return self
            except Exception as e:  # noqa: BLE001
                last_err = e
            time.sleep(0.15)
        self._teardown()
        raise AssertionError(
            f"surface-map-api daemon never became healthy on port "
            f"{self.port}: {last_err!r}"
        )

    def __exit__(self, *a):
        self._teardown()

    def _teardown(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.proc.kill()

    def fetch(self, path: str, method: str = "GET", timeout: int = 30):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}", method=method,
        )
        return urllib.request.urlopen(req, timeout=timeout)


def test_live_milestone_endpoint_payload_shape():
    """R541: GET /milestone MUST return the same shape as
    `surface-map milestone --json` — via importlib reuse of
    surface-map.py's `milestone_rollup()`."""
    with _DaemonHarness() as d:
        with d.fetch("/milestone") as r:
            assert r.status == 200
            payload = json.loads(r.read())
    missing = REQUIRED_KEYS - set(payload.keys())
    assert not missing, (
        f"/milestone payload missing required R540 keys: "
        f"{sorted(missing)}"
    )
    assert payload["module"] == "surface-map"
    assert payload["verb"] == "milestone"


def test_live_milestone_payload_carries_r539_invariants():
    """The /milestone endpoint MUST surface the R539 historic ceiling-
    closure invariants — first-class system-wide observable per R540."""
    with _DaemonHarness() as d:
        with d.fetch("/milestone") as r:
            payload = json.loads(r.read())
    assert payload["all_at_structural_ceiling"] is True
    assert payload["zero_future_waivers"] is True
    assert payload["future_carrying_count"] == 0
    assert payload["future_carrying_modules"] == []
    assert payload["full_8_surface_count"] >= 12
    assert payload["total_modules"] >= 15
    assert "R539" in payload["historic_anchor"], (
        f"/milestone historic_anchor must cite R539; "
        f"got {payload['historic_anchor']!r}"
    )
    assert payload["standing_rule"] == R453_STANDING_RULE, (
        f"/milestone standing_rule must be R453 verbatim; "
        f"got {payload['standing_rule']!r}"
    )


def test_live_milestone_matches_cli_payload():
    """API/CLI no-drift: /milestone payload MUST equal `surface-map
    milestone --json` payload — same data source via importlib reuse."""
    cp = subprocess.run(
        ["bash", str(OSCTL), "surface-map", "milestone", "--json"],
        capture_output=True, text=True, timeout=15,
        env={"PATH": "/usr/bin:/bin", "HOME": "/tmp"},
    )
    assert cp.returncode == 0, cp.stderr[:300]
    cli_payload = json.loads(cp.stdout)
    with _DaemonHarness() as d:
        with d.fetch("/milestone") as r:
            api_payload = json.loads(r.read())
    assert cli_payload == api_payload, (
        "R541: API /milestone and CLI `surface-map milestone --json` "
        "must return identical payloads (no drift)"
    )


def test_live_version_shows_r541_and_milestone_verb():
    """/version must advertise R541 in shipped_in AND list milestone
    in the verbs array — operator-§1g UX rule: every endpoint
    discoverable from /version."""
    with _DaemonHarness() as d:
        with d.fetch("/version") as r:
            payload = json.loads(r.read())
    assert "R541" in payload["shipped_in"], (
        f"/version shipped_in must mention R541; "
        f"got {payload['shipped_in']!r}"
    )
    assert "milestone" in payload.get("verbs", []), (
        f"/version verbs must include 'milestone'; "
        f"got {payload.get('verbs')!r}"
    )


def test_live_milestone_mutations_rejected_with_405():
    """Operator §17: no mutation verbs at the API surface. The
    milestone rollup is a derived read-only view; POST/PUT/DELETE/
    PATCH MUST all return 405."""
    with _DaemonHarness() as d:
        for method in ("POST", "PUT", "DELETE", "PATCH"):
            try:
                d.fetch("/milestone", method=method)
                raise AssertionError(
                    f"{method} /milestone must 405 (got 2xx)"
                )
            except urllib.error.HTTPError as e:
                assert e.code == 405, (
                    f"{method} expected 405; got {e.code}"
                )


def test_live_milestone_listed_in_404_available():
    """If an unknown path is fetched, the 404 body lists available
    endpoints — /milestone MUST be in that list post-R541."""
    with _DaemonHarness() as d:
        try:
            d.fetch("/no-such-path-r541")
        except urllib.error.HTTPError as e:
            assert e.code == 404
            body = json.loads(e.read())
    avail = body.get("available", [])
    assert "/milestone" in avail, (
        f"R541: /milestone must be advertised in 404 available list; "
        f"got {avail}"
    )


# ---------------------------------------------------- importlib reuse

def test_api_milestone_payload_uses_core_rollup():
    """The /milestone handler MUST reuse `surface-map.py`'s
    `milestone_rollup()` — no parallel implementation, no drift."""
    spec = importlib.util.spec_from_file_location("_r541", API_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert hasattr(mod, "_milestone_payload"), (
        "surface-map-api.py must define _milestone_payload"
    )
    assert hasattr(mod._core, "milestone_rollup"), (
        "surface-map.py must define milestone_rollup (the data source)"
    )
    direct = mod._core.milestone_rollup()
    via_api = mod._milestone_payload()
    assert direct == via_api, (
        "_milestone_payload MUST return the same dict as "
        "surface-map.py's milestone_rollup() (no drift)"
    )
