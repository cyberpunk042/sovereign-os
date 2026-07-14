"""Agent-layer build-configuration wiring contract (F-2026-118 / SDD-709).

SDD-703..708 built the agent layer (swappable frontend + OpenClaw + open-computer +
backend hotswap) and documented it. But every knob reached only the profile YAML and
the CLI — the operator's "proper IaC ... setup wizard ... auto-configuration" surfaces
(the build-configurator webapp + its API, and the `sovereign-osctl init` wizard) did
NOT drive them. SDD-709 wires that last mile so the wizard's checkboxes and the
build-configurator's controls set the same bake knobs the profile declares.

This lint pins the whole chain so a silent break can't half-wire it:

  1. mkosi-emit  — an env-override seam (`_env_bake`) lets SOVEREIGN_OS_BAKE_OPENCLAW /
                   _OPEN_COMPUTER ('1'/'0'/unset) + SOVEREIGN_OS_FRONTEND override the
                   profile's declared bakes.
  2. api         — build-configurator-api.py translates the POST body's frontend /
                   bake_openclaw / bake_open_computer into those env vars, validating
                   frontend against the canonical set.
  3. webapp      — index.html exposes a frontend <select> + two bake checkboxes AND
                   POSTs them + previews them in the build command.
  4. wizard      — `sovereign-osctl init` presents a 6th AGENT LAYER decision and
                   records frontend / bake_openclaw / bake_open_computer in its state.

The env-override behaviour is also exercised end-to-end (the embedded emit Python is
extracted + compiled; the wizard runs non-interactively and writes the 3 fields), so
the wiring is proven functional, not just present.
"""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
MKOSI = REPO_ROOT / "scripts" / "build" / "adapters" / "mkosi-emit.sh"
API = REPO_ROOT / "scripts" / "operator" / "build-configurator-api.py"
WEBAPP = REPO_ROOT / "webapp" / "build-configurator" / "index.html"
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"

FRONTEND_VALUES = ("gnome", "dashboards-kiosk", "open-computer-kiosk", "none")


# ---------- 1. mkosi-emit env-override seam ----------

def test_mkosi_has_env_bake_override_helper():
    body = MKOSI.read_text(encoding="utf-8")
    assert "def _env_bake(" in body, "mkosi-emit missing the _env_bake tri-state helper"
    # tri-state: '1' → True, '0' → False, unset → profile
    assert 'e == "1"' in body and 'e == "0"' in body, (
        "_env_bake is not tri-state ('1'/'0'/unset)"
    )


def test_mkosi_bakes_honor_env_override():
    body = MKOSI.read_text(encoding="utf-8")
    assert '_env_bake("SOVEREIGN_OS_BAKE_OPENCLAW"' in body, (
        "openclaw bake does not honor SOVEREIGN_OS_BAKE_OPENCLAW"
    )
    assert '_env_bake("SOVEREIGN_OS_BAKE_OPEN_COMPUTER"' in body, (
        "open-computer bake does not honor SOVEREIGN_OS_BAKE_OPEN_COMPUTER"
    )


def test_mkosi_frontend_honors_env_override():
    body = MKOSI.read_text(encoding="utf-8")
    assert 'os.environ.get("SOVEREIGN_OS_FRONTEND")' in body, (
        "frontend_default does not honor the SOVEREIGN_OS_FRONTEND env override"
    )


def test_mkosi_embedded_python_compiles():
    """The emit is a bash wrapper around one python heredoc — extract + compile it
    so a syntax error in the edited region fails here, not at build time."""
    import py_compile

    src = MKOSI.read_text(encoding="utf-8")
    blocks = re.findall(r"<<'PY'\n(.*?)\nPY", src, re.DOTALL)
    assert len(blocks) == 1, f"expected exactly 1 PY heredoc, found {len(blocks)}"
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(blocks[0])
        tmp = f.name
    try:
        py_compile.compile(tmp, doraise=True)
    finally:
        Path(tmp).unlink(missing_ok=True)


# ---------- 2. build-configurator-api translation ----------

def test_api_defines_frontend_choices_matching_canonical_set():
    body = API.read_text(encoding="utf-8")
    assert "FRONTEND_CHOICES" in body, "api missing FRONTEND_CHOICES"
    for v in FRONTEND_VALUES:
        assert f'"{v}"' in body, f"FRONTEND_CHOICES missing {v!r}"


def test_api_translates_agent_layer_body_to_bake_env():
    body = API.read_text(encoding="utf-8")
    assert 'bake_env["SOVEREIGN_OS_BAKE_OPENCLAW"]' in body, (
        "api never sets SOVEREIGN_OS_BAKE_OPENCLAW from the body"
    )
    assert 'bake_env["SOVEREIGN_OS_BAKE_OPEN_COMPUTER"]' in body, (
        "api never sets SOVEREIGN_OS_BAKE_OPEN_COMPUTER from the body"
    )
    assert 'bake_env["SOVEREIGN_OS_FRONTEND"]' in body, (
        "api never sets SOVEREIGN_OS_FRONTEND from the body"
    )
    # tri-state for the two bakes (present → '1'/'0'), and validation for frontend
    assert '"bake_openclaw" in body' in body, "api does not honor an explicit openclaw toggle"
    assert "FRONTEND_CHOICES" in body and "unknown frontend" in body, (
        "api does not validate frontend against FRONTEND_CHOICES"
    )


# ---------- 3. webapp controls ----------

def test_webapp_exposes_agent_layer_controls():
    body = WEBAPP.read_text(encoding="utf-8")
    assert 'id="bake-frontend"' in body, "webapp missing frontend selector"
    assert 'id="bake-openclaw"' in body, "webapp missing openclaw bake checkbox"
    assert 'id="bake-open_computer"' in body, "webapp missing open-computer bake checkbox"
    for v in FRONTEND_VALUES:
        assert f'value="{v}"' in body, f"webapp frontend selector missing option {v!r}"


def test_webapp_posts_agent_layer_fields():
    body = WEBAPP.read_text(encoding="utf-8")
    # the /api/run POST body carries the three fields
    assert re.search(r"frontend:\s*document\.getElementById\(.bake-frontend.\)\.value", body), (
        "webapp POST body does not send frontend"
    )
    assert re.search(r"bake_openclaw:\s*document\.getElementById\(.bake-openclaw.\)\.checked", body), (
        "webapp POST body does not send bake_openclaw"
    )
    assert re.search(
        r"bake_open_computer:\s*document\.getElementById\(.bake-open_computer.\)\.checked", body
    ), "webapp POST body does not send bake_open_computer"


def test_webapp_previews_agent_layer_env_in_command():
    body = WEBAPP.read_text(encoding="utf-8")
    assert "SOVEREIGN_OS_FRONTEND=" in body, "webapp command preview omits SOVEREIGN_OS_FRONTEND"
    assert "SOVEREIGN_OS_BAKE_OPENCLAW=1" in body, "webapp command preview omits the openclaw bake"
    assert "SOVEREIGN_OS_BAKE_OPEN_COMPUTER=1" in body, (
        "webapp command preview omits the open-computer bake"
    )


# ---------- 4. osctl init wizard ----------

def test_wizard_presents_agent_layer_decision():
    body = OSCTL.read_text(encoding="utf-8")
    assert "[6/6] AGENT LAYER" in body, "init wizard missing the [6/6] AGENT LAYER decision"
    assert "6 decisions" in body, "init wizard intro still says the old decision count"
    # the state file records all three agent-layer choices
    for field in ("frontend:", "bake_openclaw:", "bake_open_computer:"):
        assert field in body, f"init state file never records {field!r}"


def test_wizard_runs_and_records_agent_layer_fields():
    """Run the wizard non-interactively; its state file must carry the 3 new fields
    at their profile-inherit / off defaults."""
    import shutil

    env = dict(os.environ)
    env["SOVEREIGN_OS_NONINTERACTIVE"] = "1"
    proc = subprocess.run(
        ["bash", str(OSCTL), "init", "--non-interactive"],
        capture_output=True, text=True, timeout=30, env=env, cwd=str(REPO_ROOT),
    )
    assert proc.returncode == 0, f"wizard exited {proc.returncode}: {proc.stderr[:300]}"
    assert "[6/6] AGENT LAYER" in proc.stdout, "wizard did not present the agent-layer decision"
    # cmd_init writes to <repo>/.sovereign-os (gitignored); read then clean.
    state = REPO_ROOT / ".sovereign-os" / "init-state.yaml"
    try:
        data = yaml.safe_load(state.read_text(encoding="utf-8"))
    finally:
        shutil.rmtree(REPO_ROOT / ".sovereign-os", ignore_errors=True)
    d = data["decisions"]
    assert d["frontend"] == "", f"frontend should inherit the profile (empty), got {d['frontend']!r}"
    assert d["bake_openclaw"] == "no", f"bake_openclaw default wrong: {d['bake_openclaw']!r}"
    assert d["bake_open_computer"] == "no", (
        f"bake_open_computer default wrong: {d['bake_open_computer']!r}"
    )
