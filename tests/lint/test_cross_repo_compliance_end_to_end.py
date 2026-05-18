"""R469 — End-to-end meta-test for the full sovereign-os ↔ selfdef
cross-repo arc.

Synthesizes a complete operator deployment fixture (all 5 selfdef
TOML manifests + 1 modules.jsonl event stream) and runs
`sovereign-osctl compliance status --json` against it. Asserts the
aggregator reports correct data from EACH of the 5 cross-repo
instruments simultaneously.

The 5 binding paths exercised here:

  R460 master-dashboard.discover   ← SD-R-DASHBOARD-MANIFEST-1 TOMLs
  R462 surface-map selfdef         ← SD-R-MULTI-SURFACE-AUDIT-1 TOMLs
  R464 ux-design-audit selfdef     ← SD-R-UX-CHECKLIST-1 TOMLs
  R465 global-history (modules)    ← SD-R-EVENT-LOG-1 JSONL stream
  R466 anti-min-audit selfdef      ← SD-R-AUDIT-1 TOMLs

R468 bashrc-install combo is operator-runtime (interactive) and not
exercised here; the per-verb lint suite covers it.

This test is the operator's §1h "high UX/DX" / "two ultimate solutions"
acceptance criterion: a single test demonstrates the dual-repo arc
works end-to-end from selfdef-side manifest emission through
sovereign-os-side aggregation.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OP_DIR = REPO_ROOT / "scripts" / "operator"


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _synthesize_selfdef_fixture(root: Path) -> dict:
    """Build a complete selfdef deployment fixture: 5 TOML manifest
    dirs + a JSONL event stream. Returns the dict of env vars to
    point sovereign-os instruments at this fixture."""
    # 1. Dashboard manifest (R460 / SD-R-DASHBOARD-MANIFEST-1)
    dashboards_dir = root / "dashboards"
    _write(
        dashboards_dir / "agent-guard.toml",
        '''schema_version = 1

[dashboard]
module        = "agent-guard"
port          = 8090
healthz_path  = "/healthz"
subpath       = "/agent-guard/"
label         = "Agent Guard (selfdef)"
auth_tier     = "advanced"
surfaces      = ["dashboard", "api", "service"]
''',
    )
    _write(
        dashboards_dir / "polarproxy.toml",
        '''schema_version = 1

[dashboard]
module        = "polarproxy"
port          = 8443
healthz_path  = "/healthz"
subpath       = "/polarproxy/"
label         = "PolarProxy"
auth_tier     = "basic"
''',
    )

    # 2. Surface manifest (R462 / SD-R-MULTI-SURFACE-AUDIT-1)
    surfaces_dir = root / "surfaces"
    _write(
        surfaces_dir / "agent-guard.toml",
        '''schema_version = 1

[module]
id    = "agent-guard"
label = "Agent Guard"

[[surfaces]]
id    = "core"
state = "shipped"

[[surfaces]]
id    = "cli"
state = "shipped"

[[surfaces]]
id    = "service"
state = "shipped"

[[surfaces]]
id     = "tui"
state  = "waived"
reason = "daemon — no interactive surface"
''',
    )

    # 3. UX checklist (R464 / SD-R-UX-CHECKLIST-1)
    ux_dir = root / "ux-checklists"
    _write(
        ux_dir / "agent-guard.toml",
        '''schema_version = 1

[module]
id    = "agent-guard"
label = "Agent Guard"

[[dimensions]]
id    = "action-budget"
state = "pass"

[[dimensions]]
id    = "discoverable"
state = "pass"

[[dimensions]]
id     = "recoverable"
state  = "n-a"
reason = "read-only event consumer"

[[dimensions]]
id    = "next-step"
state = "pass"

[[dimensions]]
id    = "operator-named"
state = "pass"

[[dimensions]]
id    = "readable-30s"
state = "pass"
''',
    )

    # 4. Audit manifest (R466 / SD-R-AUDIT-1)
    audit_dir = root / "audit-manifests"
    _write(
        audit_dir / "agent-guard.toml",
        '''schema_version = 1

[module]
id    = "agent-guard"
label = "Agent Guard"

[[findings]]
pattern = "todo-no-anchor"
count   = 0

[[findings]]
pattern = "empty-stub"
count   = 0

[[findings]]
pattern = "minimize-phrase"
count   = 2
note    = "two operator-named uses in policy docs"
''',
    )

    # 5. modules.jsonl event stream (R465 / SD-R-EVENT-LOG-1)
    events_log = root / "modules.jsonl"
    events_log.write_text(
        "\n".join([
            json.dumps({
                "timestamp": "2026-05-18T16:00:00Z",
                "source": "modules",
                "module": "agent-guard",
                "event": "installed",
                "status": "ok",
                "actor": "selfdefctl",
            }),
            json.dumps({
                "timestamp": "2026-05-18T16:01:00Z",
                "source": "modules",
                "module": "polarproxy",
                "event": "feature-toggled",
                "status": "ok",
                "detail": {"feature": "tls-mitm"},
            }),
        ]) + "\n",
        encoding="utf-8",
    )

    return {
        "SOVEREIGN_OS_SELFDEF_MANIFEST_DIR": str(dashboards_dir),
        "SOVEREIGN_OS_SELFDEF_SURFACE_DIR": str(surfaces_dir),
        "SOVEREIGN_OS_SELFDEF_UX_DIR": str(ux_dir),
        "SOVEREIGN_OS_SELFDEF_AUDIT_DIR": str(audit_dir),
        "SOVEREIGN_OS_MODULES_LOG": str(events_log),
    }


def test_full_cross_repo_arc_end_to_end(tmp_path):
    """Master integration test: synthesize a complete selfdef
    deployment fixture, run `compliance status`, assert ALL 5
    cross-repo binding paths return correct data simultaneously."""
    env_overrides = _synthesize_selfdef_fixture(tmp_path)
    result = subprocess.run(
        ["python3", str(OP_DIR / "compliance.py"), "status", "--json"],
        capture_output=True, text=True, timeout=240,
        env={**os.environ, **env_overrides},
    )
    assert result.returncode == 0, (
        f"compliance status failed: stderr={result.stderr[:500]}"
    )
    data = json.loads(result.stdout)

    # ---- R460 master-dashboard.discover ----
    sd = data["selfdef_discovery"]
    assert sd["available"] is True
    assert sd["discovered_count"] == 2, (
        f"expected 2 dashboards (agent-guard + polarproxy), "
        f"got {sd['discovered_count']}"
    )
    assert sd["errors"] == []
    # Operator-§1g "operator-discoverable collisions": none expected
    # against our synthetic fixture's slugs.
    # (Note: built-in DASHBOARD_ROUTES may collide with synthetic
    # slugs ONLY if we picked colliding names; we picked
    # agent-guard + polarproxy which aren't in the built-in set.)

    # ---- R462 surface-map selfdef ----
    ss = data["selfdef_surfaces"]
    assert ss["available"] is True
    assert ss["discovered_count"] == 1
    assert ss["total_shipped_surfaces"] == 3, (
        "agent-guard fixture ships core+cli+service (3 surfaces)"
    )
    assert ss["errors"] == []

    # ---- R464 ux-design-audit selfdef ----
    sux = data["selfdef_ux"]
    assert sux["available"] is True
    assert sux["discovered_count"] == 1
    # agent-guard fixture has 5 pass + 1 n-a + 0 fail
    assert sux["total_pass"] == 5
    assert sux["total_fail"] == 0
    assert sux["errors"] == []

    # ---- R466 anti-min-audit selfdef ----
    sa = data["selfdef_audit"]
    assert sa["available"] is True
    assert sa["discovered_count"] == 1
    # agent-guard fixture has 0 + 0 + 2 = 2 findings
    assert sa["total_findings"] == 2
    assert sa["errors"] == []

    # ---- R465 global-history modules reader ----
    # global-history doesn't appear in compliance directly; verify
    # it picks up the JSONL stream via the env override.
    gh = subprocess.run(
        ["python3", str(OP_DIR / "global-history.py"), "recent",
         "--source", "modules",
         "--since", "2020-01-01T00:00:00Z", "--json"],
        capture_output=True, text=True, timeout=30,
        env={**os.environ, **env_overrides},
    )
    assert gh.returncode == 0
    gh_data = json.loads(gh.stdout)
    events = gh_data.get("events", [])
    assert len(events) == 2, (
        f"expected 2 module events, got {len(events)}: {events}"
    )
    actions = [e.get("action", "") for e in events]
    detail_blobs = [e.get("detail", "") for e in events]
    assert any("installed" in str(a) for a in actions) \
        or any("installed" in str(d) for d in detail_blobs), (
            "expected 'installed' event from agent-guard"
        )

    # ---- Sovereign-os-internal instruments still report ----
    for k in ("surface_map", "doc_coverage",
              "anti_minimization_audit", "ux_design_audit"):
        assert data[k]["available"] is True, (
            f"sovereign-os-internal {k} not available"
        )


def test_dashboard_manifest_drift_surfaces_as_error(tmp_path):
    """If a selfdef manifest declares an unsupported schema_version,
    the consumer surfaces it as an error (operator-discoverable,
    not silent ignore)."""
    env_overrides = _synthesize_selfdef_fixture(tmp_path)
    # Inject a corrupt manifest
    bad_path = tmp_path / "dashboards" / "broken.toml"
    bad_path.write_text(
        '''schema_version = 99

[dashboard]
module = "broken"
''',
        encoding="utf-8",
    )
    result = subprocess.run(
        ["python3", str(OP_DIR / "master-dashboard.py"),
         "discover", "--json"],
        capture_output=True, text=True, timeout=15,
        env={**os.environ, **env_overrides},
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert len(data["errors"]) >= 1, (
        "future schema_version should surface as discovery error"
    )
    assert data["count"] == 2, (
        "valid manifests must still load even when sibling is bad"
    )


def test_event_stream_reader_recovers_from_partial_corruption(tmp_path):
    """If the modules.jsonl file has interleaved malformed lines,
    the reader skips them but processes valid records."""
    env_overrides = _synthesize_selfdef_fixture(tmp_path)
    events_log = Path(env_overrides["SOVEREIGN_OS_MODULES_LOG"])
    # Append a malformed line + a valid line
    with events_log.open("a", encoding="utf-8") as f:
        f.write("not-json-at-all\n")
        f.write(json.dumps({
            "timestamp": "2026-05-18T16:02:00Z",
            "source": "modules",
            "module": "agent-guard",
            "event": "policy-applied",
            "status": "ok",
        }) + "\n")
    gh = subprocess.run(
        ["python3", str(OP_DIR / "global-history.py"), "recent",
         "--source", "modules",
         "--since", "2020-01-01T00:00:00Z", "--json"],
        capture_output=True, text=True, timeout=30,
        env={**os.environ, **env_overrides},
    )
    assert gh.returncode == 0
    gh_data = json.loads(gh.stdout)
    events = gh_data.get("events", [])
    # 2 original valid + 1 new valid = 3; the malformed line is skipped
    assert len(events) == 3, (
        f"expected 3 valid events (1 malformed line skipped), "
        f"got {len(events)}: {events}"
    )


def test_synthesized_fixture_lints_clean_via_each_consumer(tmp_path):
    """Defense-in-depth: every consumer verb runs cleanly on the
    fixture (no errors / collisions / schema mismatches)."""
    env_overrides = _synthesize_selfdef_fixture(tmp_path)
    env = {**os.environ, **env_overrides}
    verbs = [
        ("master-dashboard.py", "discover"),
        ("surface-map.py", "selfdef"),
        ("ux-design-audit.py", "selfdef"),
        ("anti-minimization-audit.py", "selfdef"),
    ]
    for script, verb in verbs:
        r = subprocess.run(
            ["python3", str(OP_DIR / script), verb, "--json"],
            capture_output=True, text=True, timeout=30, env=env,
        )
        assert r.returncode == 0, (
            f"{script} {verb} failed: stderr={r.stderr[:300]}"
        )
        d = json.loads(r.stdout)
        assert d["count"] >= 1, (
            f"{script} {verb} found 0 manifests; fixture broken?"
        )
        assert d["errors"] == [], (
            f"{script} {verb} surfaced errors: {d['errors']}"
        )
