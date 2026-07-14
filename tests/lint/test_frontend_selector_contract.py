"""Swappable boot-frontend selector contract (F-2026-113 / SDD-704).

The operator asked to "chose at any point to start in one or another or even disable
both" — a frontend the box presents that is build-time-default AND runtime-switchable.
SDD-704 delivers it as one coherent chain across six seams; a silent break in any one
leaves the selector half-wired (e.g. the profile field exists but mkosi never passes
it, or the kiosk unit exists but nothing enables it). This lint pins the whole chain:

  1. schema     — provisioning.frontend {default enum, install enum}
  2. profile    — sain-01 declares provisioning.frontend.default + install
  3. mkosi-emit — parses prov.frontend + emits SOVEREIGN_OS_FRONTEND(_INSTALL)
  4. installer  — install-gui-dashboards.sh reads the frontend, stages the kiosk
                  stack, activates the default
  5. unit       — sovereign-frontend-kiosk.service exists, is enable-able, carries the
                  hardening waiver + universal clauses, ExecStarts the launcher
  6. cli        — frontend.py (status/list/set, 4 frontends, dry-run) + osctl verb + help

Behaviour is also exercised (frontend.py runs in dry-run: list/status/set write the
kiosk env + reject unknown values), so the selector is proven functional, not just
present.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA = REPO_ROOT / "schemas" / "profile.schema.yaml"
PROFILE = REPO_ROOT / "profiles" / "sain-01.yaml"
MKOSI = REPO_ROOT / "scripts" / "build" / "adapters" / "mkosi-emit.sh"
INSTALLER = REPO_ROOT / "scripts" / "install" / "install-gui-dashboards.sh"
KIOSK_UNIT = REPO_ROOT / "systemd" / "system" / "sovereign-frontend-kiosk.service"
LAUNCHER = REPO_ROOT / "scripts" / "operator" / "frontend-kiosk.sh"
FRONTEND_PY = REPO_ROOT / "scripts" / "operator" / "frontend.py"
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"

FRONTEND_VALUES = ("gnome", "dashboards-kiosk", "open-computer-kiosk", "none")


# ---------- 1. schema ----------

def test_schema_defines_frontend_block():
    doc = yaml.safe_load(SCHEMA.read_text(encoding="utf-8"))
    props = doc["properties"]["provisioning"]["properties"]
    assert "frontend" in props, "schema provisioning.frontend missing (SDD-704)"
    fe = props["frontend"]
    assert fe.get("additionalProperties") is False, "frontend must be additionalProperties:false"
    default_enum = fe["properties"]["default"]["enum"]
    assert set(default_enum) == set(FRONTEND_VALUES), (
        f"frontend.default enum {default_enum} != {FRONTEND_VALUES}"
    )
    install_enum = fe["properties"]["install"]["items"]["enum"]
    # install is the stageable stacks (no 'none' — you can't stage nothing)
    assert set(install_enum) == set(FRONTEND_VALUES) - {"none"}, (
        f"frontend.install enum {install_enum} unexpected"
    )


# ---------- 2. profile ----------

def test_profile_declares_frontend():
    doc = yaml.safe_load(PROFILE.read_text(encoding="utf-8"))
    fe = doc["provisioning"]["frontend"]
    assert fe["default"] in FRONTEND_VALUES, f"sain-01 frontend.default {fe['default']!r} invalid"
    assert isinstance(fe["install"], list) and fe["install"], "sain-01 frontend.install must be a non-empty list"
    for v in fe["install"]:
        assert v in set(FRONTEND_VALUES) - {"none"}, f"sain-01 frontend.install has invalid {v!r}"


def test_profile_default_gnome_is_behaviour_preserving():
    """The recommended provisional default (SDD-703 D1) is gnome — least surprise,
    preserves today's boot behaviour. A drift here is an intentional operator call."""
    doc = yaml.safe_load(PROFILE.read_text(encoding="utf-8"))
    assert doc["provisioning"]["frontend"]["default"] == "gnome"


# ---------- 3. mkosi-emit ----------

def test_mkosi_parses_and_emits_frontend():
    body = MKOSI.read_text(encoding="utf-8")
    assert 'prov.get("frontend")' in body, "mkosi-emit does not parse provisioning.frontend"
    assert "SOVEREIGN_OS_FRONTEND=" in body, "mkosi-emit does not emit SOVEREIGN_OS_FRONTEND"
    assert "SOVEREIGN_OS_FRONTEND_INSTALL=" in body, "mkosi-emit does not emit SOVEREIGN_OS_FRONTEND_INSTALL"


# ---------- 4. installer ----------

def test_installer_reads_and_activates_frontend():
    body = INSTALLER.read_text(encoding="utf-8")
    assert "SOVEREIGN_OS_FRONTEND" in body, "installer ignores SOVEREIGN_OS_FRONTEND"
    assert "install_kiosk_stack" in body, "installer has no kiosk-stack install path"
    # every frontend value handled in the default-activation case
    for v in FRONTEND_VALUES:
        assert v in body, f"installer does not handle frontend value {v!r}"
    assert "sovereign-frontend-kiosk.service" in body, "installer never references the kiosk unit"


# ---------- 5. kiosk unit ----------

def test_kiosk_unit_exists_and_installable():
    body = KIOSK_UNIT.read_text(encoding="utf-8")
    assert "[Install]" in body, "kiosk unit has no [Install] (unreachable / can't be enabled)"
    assert "WantedBy=graphical.target" in body, "kiosk unit not wired to graphical.target"
    assert "ExecStart=" in body and "frontend-kiosk.sh" in body, "kiosk unit does not ExecStart the launcher"


def test_kiosk_unit_hardening_shape():
    """The kiosk carries the whole-service waiver (a graphical session can't sandbox
    fully) AND still every universal fleet-hardening clause."""
    body = KIOSK_UNIT.read_text(encoding="utf-8")
    assert "# HARDENING-WAIVER:" in body, "kiosk unit missing HARDENING-WAIVER"
    for clause in ("NoNewPrivileges=true", "ProtectControlGroups=true",
                   "RestrictRealtime=true", "ProtectKernelTunables=true"):
        assert clause in body, f"kiosk unit missing universal clause {clause}"
    assert ("ProtectSystem=full" in body or "ProtectSystem=strict" in body), (
        "kiosk unit missing ProtectSystem=full|strict"
    )


def test_kiosk_launcher_exists_executable_strict():
    assert LAUNCHER.is_file(), "kiosk launcher missing"
    assert os.access(LAUNCHER, os.X_OK), "kiosk launcher not executable"
    body = LAUNCHER.read_text(encoding="utf-8")
    assert "set -euo pipefail" in body, "kiosk launcher missing bash strict mode"
    assert "cage" in body, "kiosk launcher does not use the cage compositor"


# ---------- 6. cli ----------

def test_frontend_py_shape():
    body = FRONTEND_PY.read_text(encoding="utf-8")
    for verb in ("status", "list", "set"):
        assert f'"{verb}"' in body, f"frontend.py missing the {verb!r} subcommand"
    for v in FRONTEND_VALUES:
        assert v in body, f"frontend.py missing frontend value {v!r}"
    assert "SOVEREIGN_OS_FRONTEND_DRYRUN" in body, "frontend.py has no dry-run seam (untestable without root)"


def test_osctl_dispatches_frontend_and_documents_it():
    body = OSCTL.read_text(encoding="utf-8")
    assert "frontend)" in body, "osctl has no frontend) dispatch case"
    assert "scripts/operator/frontend.py" in body, "osctl frontend verb doesn't delegate to frontend.py"
    assert "frontend status" in body and "frontend set" in body, (
        "osctl help does not document the frontend verb (DX gap)"
    )


# ---------- behaviour (dry-run) ----------

def _run_frontend(args: list[str], tmp: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["SOVEREIGN_OS_FRONTEND_DRYRUN"] = "1"
    env["SOVEREIGN_OS_FRONTEND_STATE"] = str(tmp / "frontend.active")
    env["SOVEREIGN_OS_FRONTEND_KIOSK_ENV"] = str(tmp / "kiosk.env")
    return subprocess.run(
        [sys.executable, str(FRONTEND_PY), *args],
        capture_output=True, text=True, env=env, timeout=30,
    )


def test_frontend_set_writes_kiosk_env(tmp_path: Path):
    r = _run_frontend(["set", "dashboards-kiosk"], tmp_path)
    assert r.returncode == 0, f"set dashboards-kiosk failed: {r.stderr}"
    env = (tmp_path / "kiosk.env").read_text(encoding="utf-8")
    assert "FRONTEND_KIOSK_URL=http://127.0.0.1:8100/" in env, "kiosk env URL not written for dashboards-kiosk"
    assert (tmp_path / "frontend.active").read_text(encoding="utf-8").strip() == "dashboards-kiosk"


def test_frontend_set_custom_url(tmp_path: Path):
    r = _run_frontend(["set", "open-computer-kiosk", "--url", "http://127.0.0.1:9999/"], tmp_path)
    assert r.returncode == 0, r.stderr
    env = (tmp_path / "kiosk.env").read_text(encoding="utf-8")
    assert "http://127.0.0.1:9999/" in env, "--url override not honoured"


def test_frontend_list_json_is_pure(tmp_path: Path):
    """--json stdout must be parseable (dry-run systemctl logs go to stderr)."""
    import json
    r = _run_frontend(["list", "--json"], tmp_path)
    assert r.returncode == 0, r.stderr
    doc = json.loads(r.stdout)
    got = {row["frontend"] for row in doc["frontends"]}
    assert got == set(FRONTEND_VALUES), f"frontend.py list frontends {got} != {FRONTEND_VALUES}"


def test_frontend_rejects_unknown(tmp_path: Path):
    r = _run_frontend(["set", "bogus"], tmp_path)
    assert r.returncode != 0, "frontend.py accepted an unknown frontend value"
