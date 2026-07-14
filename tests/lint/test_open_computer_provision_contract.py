"""open-computer QEMU AI-sandbox provisioning contract (F-2026-114 / SDD-706).

The operator flagged open-computer as "an interesting alternative that I might wanna be
able to hotswap". It's a QEMU VM (Debian guest + XFCE + Chromium) an AI agent drives,
consuming a local OpenAI-compatible LLM — installed-off, first-boot-provisioned (QEMU/KVM
+ Node + a repo build + a ~3GB base image, none reachable at image build). This lint pins
the whole chain so it can't land half-wired:

  1. schema     — bake.open_computer + provisioning.open_computer {endpoint, model_id,
                  web_port, repo, base_image_url, node_major}
  2. profile    — sain-01 opts in + points at the local endpoint + the verified :9800 UI port
  3. mkosi-emit — parses bake.open_computer + emits SOVEREIGN_OS_BAKE_OPEN_COMPUTER
  4. provision-bake — stages the units + enables ONLY the first-boot installer
  5. hook       — QEMU/KVM install, resumable base-image pull, LLM preconfig (OPENAI_BASE_URL
                  → the local endpoint), non-fatal skips, no external channels, idempotent
  6. units      — first-boot installer (full R171, no waiver) + runtime daemon
                  (installed-off, /dev/kvm-gated, VM-host waiver + compatible clauses)
  7. cli        — sovereign-osctl open-computer {status|on|off|install|url|logs|doctor}
  8. selector   — frontend.py open-computer-kiosk points at the verified :9800 UI
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA = REPO_ROOT / "schemas" / "profile.schema.yaml"
PROFILE = REPO_ROOT / "profiles" / "sain-01.yaml"
MKOSI = REPO_ROOT / "scripts" / "build" / "adapters" / "mkosi-emit.sh"
PROVISION = REPO_ROOT / "scripts" / "build" / "provision-bake.sh"
HOOK = REPO_ROOT / "scripts" / "hooks" / "post-install" / "open-computer-install.sh"
RUN = REPO_ROOT / "scripts" / "operator" / "open-computer-run.sh"
INSTALL_UNIT = REPO_ROOT / "systemd" / "system" / "sovereign-open-computer-install.service"
RUNTIME_UNIT = REPO_ROOT / "systemd" / "system" / "sovereign-open-computer.service"
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"
FRONTEND_PY = REPO_ROOT / "scripts" / "operator" / "frontend.py"


# ---------- 1. schema ----------

def test_schema_bake_and_open_computer_block():
    doc = yaml.safe_load(SCHEMA.read_text(encoding="utf-8"))
    prov = doc["properties"]["provisioning"]["properties"]
    assert "open_computer" in prov["bake"]["properties"], "schema bake.open_computer missing"
    oc = prov["open_computer"]
    assert oc.get("additionalProperties") is False
    for f in ("endpoint", "model_id", "web_port", "repo", "base_image_url", "node_major"):
        assert f in oc["properties"], f"schema provisioning.open_computer.{f} missing"


# ---------- 2. profile ----------

def test_profile_opts_in_local_endpoint_and_9800():
    doc = yaml.safe_load(PROFILE.read_text(encoding="utf-8"))
    assert doc["provisioning"]["bake"].get("open_computer") is True, "sain-01 does not bake.open_computer"
    oc = doc["provisioning"]["open_computer"]
    assert oc["endpoint"].startswith("http://127.0.0.1"), f"endpoint {oc['endpoint']!r} not loopback-local"
    assert int(oc["web_port"]) == 9800, "open-computer web_port should be the verified 9800"
    assert "anything-llm" in oc["repo"] or "Mintplex" in oc["repo"], "repo is not the Mintplex anything-llm upstream"
    assert oc["base_image_url"].endswith(".tar"), "base_image_url should be the CDN tar asset"


# ---------- 3. mkosi-emit ----------

def test_mkosi_emits_bake_open_computer():
    body = MKOSI.read_text(encoding="utf-8")
    assert 'prov_bake.get("open_computer")' in body, "mkosi-emit does not parse bake.open_computer"
    assert "SOVEREIGN_OS_BAKE_OPEN_COMPUTER=" in body, "mkosi-emit does not emit SOVEREIGN_OS_BAKE_OPEN_COMPUTER"


# ---------- 4. provision-bake ----------

def test_provision_stages_units_installer_only():
    body = PROVISION.read_text(encoding="utf-8")
    assert "SOVEREIGN_OS_BAKE_OPEN_COMPUTER" in body, "provision-bake ignores the open_computer bake gate"
    assert re.search(r"systemctl enable sovereign-open-computer-install\.service", body), (
        "provision-bake must enable ONLY the installer"
    )
    assert not re.search(r"systemctl enable[^\n]*\bsovereign-open-computer\.service\b", body), (
        "provision-bake must NOT enable the runtime daemon (breaks installed-off posture)"
    )


# ---------- 5. hook ----------

def test_hook_qemu_baseimage_localendpoint_nonfatal():
    body = HOOK.read_text(encoding="utf-8")
    assert "set -euo pipefail" in body, "hook missing bash strict mode"
    assert "qemu-system-x86" in body, "hook does not install QEMU"
    assert "OPENAI_BASE_URL" in body, "hook does not preconfigure the LLM backend"
    assert "provisioning.open_computer.endpoint" in body, "hook does not read the profile endpoint"
    # Resumable base-image pull (upstream's fetch script is NOT resumable — we use curl -C -).
    assert "curl -fL -C -" in body, "hook base-image download is not resumable (curl -C -)"
    assert "sha256" in body, "hook does not verify the base image checksum"
    # Non-fatal discipline: many skip paths for a heavy first-boot provision.
    assert body.count("exit 0") >= 4, "hook lacks the non-fatal skip paths"


def test_hook_bakes_no_external_channels():
    active = "\n".join(
        ln for ln in HOOK.read_text(encoding="utf-8").splitlines()
        if not ln.lstrip().startswith("#")
    ).lower()
    for channel in ("whatsapp", "telegram", "discord", "slack", "imessage"):
        assert channel not in active, f"hook bakes a {channel} channel — must ship channel-free (SDD-703 D5)"


def test_hook_and_launcher_executable():
    import os
    for f in (HOOK, RUN):
        assert f.is_file() and os.access(f, os.X_OK), f"{f.name} missing or not executable"


# ---------- 6. units ----------

def test_installer_unit_first_boot_full_hardening():
    body = INSTALL_UNIT.read_text(encoding="utf-8")
    assert "ConditionFirstBoot=yes" in body, "installer must be first-boot only"
    assert "openclaw" not in body.lower(), "installer references the wrong component"
    assert "open-computer-install.sh" in body, "installer does not run the hook"
    # The provisioner writes no /home → full R171, no waiver.
    assert "# HARDENING-WAIVER:" not in body, "installer should NOT need a waiver (writes /var, not /home)"
    assert "ProtectHome=true" in body, "installer ProtectHome should be true"


def test_runtime_unit_kvm_gated_installed_off_waived():
    body = RUNTIME_UNIT.read_text(encoding="utf-8")
    assert "ExecStart=" in body and "open-computer-run.sh" in body, "runtime unit does not run the launcher"
    assert "ConditionPathExists=/dev/kvm" in body, "runtime must be /dev/kvm-gated"
    assert "[Install]" in body, "runtime unit has no [Install]"
    # A QEMU/KVM VM host legitimately carries a waiver, plus the universal clauses.
    assert "# HARDENING-WAIVER:" in body, "VM-host runtime missing the documented waiver"
    for clause in ("NoNewPrivileges=true", "ProtectControlGroups=true",
                   "RestrictRealtime=true", "ProtectKernelTunables=true", "ProtectSystem=strict"):
        assert clause in body, f"runtime unit missing universal clause {clause}"
    assert "ReadWritePaths=/var/lib/sovereign-os/open-computer" in body, "runtime RWP not scoped to its state dir"


# ---------- 7. cli ----------

def test_osctl_open_computer_verb():
    body = OSCTL.read_text(encoding="utf-8")
    assert "cmd_open_computer()" in body, "osctl missing cmd_open_computer handler"
    assert re.search(r"^\s*open-computer\)\s+cmd_open_computer\b", body, re.M), "osctl does not dispatch open-computer"
    for verb in ("open-computer status", "open-computer on", "open-computer install"):
        assert verb in body, f"osctl help does not document '{verb}'"


# ---------- 8. selector wiring ----------

def test_frontend_kiosk_points_at_9800():
    body = FRONTEND_PY.read_text(encoding="utf-8")
    # Match the DEFAULT_KIOSK_URL entry specifically (an http(s) value, not the description).
    m = re.search(r'"open-computer-kiosk":\s*"(https?://[^"]+)"', body)
    assert m, "frontend.py has no open-computer-kiosk default URL"
    assert "9800" in m.group(1), f"open-computer-kiosk URL {m.group(1)!r} does not target the verified :9800 UI"
