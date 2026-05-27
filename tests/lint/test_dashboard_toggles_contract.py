"""M060 R10038 + R10129-R10132 — operator dashboard on/off toggle contract.

Materializes the operator standing direction "everything can be turned on and
off". Every cockpit dashboard can be toggled; state persists in
/etc/sovereign-os/dashboards.toml (R10130); enable/disable is the operator CLI
path (R10131); each toggle emits an M049 trace + OCSF 5001 Configuration Change
(R10132) into the D-05 span log.

  core  scripts/manifest/dashboard-toggles.py
  cli   sovereign-osctl dashboards {list,status,enable,disable}
  view  master-dashboard.py toggles
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CORE = REPO_ROOT / "scripts" / "manifest" / "dashboard-toggles.py"
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"
MASTER = REPO_ROOT / "scripts" / "operator" / "master-dashboard.py"
WEBAPP_DIR = REPO_ROOT / "webapp"


def _run(args, **env):
    return subprocess.run(
        ["python3", str(CORE), *args],
        capture_output=True, text=True, timeout=15, check=True,
        env={**os.environ, **env},
    )


def test_core_present():
    assert CORE.is_file(), f"core missing: {CORE}"


def test_catalog_is_real_webapp_dirs():
    """The toggle catalog must be the real shipped dashboards (webapp/*/), not
    invented — every listed slug has a webapp/<slug>/index.html."""
    out = _run(["list"], SOVEREIGN_OS_DASHBOARDS_TOML="/tmp/sovereign-os-no-dash.toml")
    d = json.loads(out.stdout)
    assert d["total"] >= 20, "must enumerate the 20+ cockpit dashboards"
    for r in d["dashboards"]:
        if r["on_disk"]:
            assert (WEBAPP_DIR / r["slug"] / "index.html").is_file(), \
                f"catalogued {r['slug']} has no webapp dir"


def test_default_all_enabled():
    """Absent toml → every dashboard enabled (ships ON; operator opts out)."""
    out = _run(["list"], SOVEREIGN_OS_DASHBOARDS_TOML="/tmp/sovereign-os-no-dash.toml")
    d = json.loads(out.stdout)
    assert d["toml_present"] is False
    assert d["disabled_count"] == 0 and d["enabled_count"] == d["total"]


def test_disable_persists_and_emits_ocsf_5001():
    """disable writes the toml (R10130) + emits an OCSF 5001 span (R10132)."""
    with tempfile.TemporaryDirectory() as tmp:
        toml = os.path.join(tmp, "dashboards.toml")
        spans = os.path.join(tmp, "spans.jsonl")
        out = _run(["disable", "d-04-costs", "--rationale", "test"],
                   SOVEREIGN_OS_DASHBOARDS_TOML=toml, SOVEREIGN_OS_SPAN_STORE=spans)
        r = json.loads(out.stdout)
        assert r["ok"] and r["changed"] and r["now"] is False
        assert r["ocsf_5001_traced"] is True
        # toml persisted with the disabled bit
        assert os.path.isfile(toml)
        assert "d-04-costs = false" in Path(toml).read_text()
        # OCSF 5001 Configuration Change span emitted into the D-05 span log
        span = json.loads(Path(spans).read_text().strip().splitlines()[-1])
        assert span["ocsf_class"] == "5001"
        assert span["operation"] == "dashboard_toggle"
        assert span["attributes"]["dashboard"] == "d-04-costs"
        assert span["attributes"]["enabled"] is False
        # status reflects it
        st = _run(["status", "d-04-costs"], SOVEREIGN_OS_DASHBOARDS_TOML=toml)
        assert json.loads(st.stdout)["enabled"] is False
        # re-enable round-trips
        out2 = _run(["enable", "d-04-costs"],
                    SOVEREIGN_OS_DASHBOARDS_TOML=toml, SOVEREIGN_OS_SPAN_STORE=spans)
        assert json.loads(out2.stdout)["now"] is True


def test_unknown_slug_rejected():
    with tempfile.TemporaryDirectory() as tmp:
        toml = os.path.join(tmp, "dashboards.toml")
        out = subprocess.run(
            ["python3", str(CORE), "disable", "bogus-dash"],
            capture_output=True, text=True, timeout=15,
            env={**os.environ, "SOVEREIGN_OS_DASHBOARDS_TOML": toml},
        )
        assert out.returncode == 2
        assert json.loads(out.stdout)["ok"] is False


def test_osctl_dispatches_dashboards():
    body = OSCTL.read_text(encoding="utf-8")
    assert "dashboards)" in body, "osctl missing dashboards dispatch case"
    assert "scripts/manifest/dashboard-toggles.py" in body


def test_master_dashboard_toggles_subcommand():
    """The aggregator surfaces the on/off state via `master-dashboard toggles`."""
    with tempfile.TemporaryDirectory() as tmp:
        toml = os.path.join(tmp, "dashboards.toml")
        out = subprocess.run(
            ["python3", str(MASTER), "toggles", "--json"],
            capture_output=True, text=True, timeout=15, check=True,
            env={**os.environ, "SOVEREIGN_OS_DASHBOARDS_TOML": toml},
        )
        d = json.loads(out.stdout)
        assert "dashboards" in d and d["total"] >= 20
        assert d["enabled_count"] == d["total"]  # nothing disabled in fresh toml
