"""OpenClaw agent-runtime provisioning contract (F-2026-115 / SDD-705).

The operator asked to "include OpenClaw in the options of the build … add the
preconfiguration options". OpenClaw is a Node gateway daemon that must point at the
LOCAL vLLM endpoint (SDD-702) — installed-off, first-boot-provisioned (no network at
image build). This lint pins the whole chain so it can't land half-wired:

  1. schema     — bake.openclaw + provisioning.openclaw {endpoint, model_id,
                  gateway_port, node_major}
  2. profile    — sain-01 opts in + points at the local endpoint
  3. mkosi-emit — parses bake.openclaw + emits SOVEREIGN_OS_BAKE_OPENCLAW
  4. provision-bake — stages the units + enables ONLY the first-boot installer
                  (runtime daemon stays installed-off)
  5. hook       — openclaw-install.sh: Node engines-band check, npm -g openclaw,
                  renders the preconfig → the local endpoint, non-fatal skips, no
                  external channels baked, idempotent
  6. units      — the first-boot installer (VM-tolerant, first-boot) + the runtime
                  daemon (installed-off, HOME relocated so it stays hardened)
  7. cli        — sovereign-osctl openclaw {status|on|off|install|logs|doctor}

Verifies the local-endpoint wiring + the "no external channels" posture (SDD-703 D5)
concretely, so a future edit can't silently point it at a cloud provider or bake a
channel credential.
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
HOOK = REPO_ROOT / "scripts" / "hooks" / "post-install" / "openclaw-install.sh"
INSTALL_UNIT = REPO_ROOT / "systemd" / "system" / "sovereign-openclaw-install.service"
RUNTIME_UNIT = REPO_ROOT / "systemd" / "system" / "sovereign-openclaw.service"
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"


# ---------- 1. schema ----------

def test_schema_bake_and_openclaw_block():
    doc = yaml.safe_load(SCHEMA.read_text(encoding="utf-8"))
    prov = doc["properties"]["provisioning"]["properties"]
    assert "openclaw" in prov["bake"]["properties"], "schema bake.openclaw missing"
    oc = prov["openclaw"]
    assert oc.get("additionalProperties") is False
    for f in ("endpoint", "model_id", "gateway_port", "node_major"):
        assert f in oc["properties"], f"schema provisioning.openclaw.{f} missing"


# ---------- 2. profile ----------

def test_profile_opts_in_local_endpoint():
    doc = yaml.safe_load(PROFILE.read_text(encoding="utf-8"))
    assert doc["provisioning"]["bake"].get("openclaw") is True, "sain-01 does not bake.openclaw"
    oc = doc["provisioning"]["openclaw"]
    # Points at a LOCAL loopback endpoint (not a cloud provider)
    assert oc["endpoint"].startswith("http://127.0.0.1"), (
        f"openclaw endpoint {oc['endpoint']!r} is not loopback-local"
    )
    assert int(oc["gateway_port"]) == 18789, "openclaw gateway_port should default to 18789"
    # Node major must satisfy OpenClaw's engines band (>=22.22.3 <23 or >=24.15 <25)
    assert int(oc["node_major"]) in (22, 24, 25), f"node_major {oc['node_major']} unlikely to satisfy OpenClaw engines"


# ---------- 3. mkosi-emit ----------

def test_mkosi_emits_bake_openclaw():
    body = MKOSI.read_text(encoding="utf-8")
    assert 'prov_bake.get("openclaw")' in body, "mkosi-emit does not parse bake.openclaw"
    assert "SOVEREIGN_OS_BAKE_OPENCLAW=" in body, "mkosi-emit does not emit SOVEREIGN_OS_BAKE_OPENCLAW"


# ---------- 4. provision-bake ----------

def test_provision_stages_units_installer_only():
    body = PROVISION.read_text(encoding="utf-8")
    assert "SOVEREIGN_OS_BAKE_OPENCLAW" in body, "provision-bake ignores the openclaw bake gate"
    assert "sovereign-openclaw-install.service" in body, "provision-bake never enables the first-boot installer"
    # The runtime daemon must NOT be enabled at bake time (installed-off posture):
    # only the installer is enabled.
    assert re.search(r"systemctl enable sovereign-openclaw-install\.service", body), (
        "provision-bake must enable ONLY the installer (runtime stays installed-off)"
    )
    assert not re.search(r"systemctl enable[^\n]*\bsovereign-openclaw\.service\b", body), (
        "provision-bake must NOT enable the runtime daemon (breaks installed-off posture)"
    )


# ---------- 5. hook ----------

def test_hook_local_endpoint_and_non_fatal():
    body = HOOK.read_text(encoding="utf-8")
    assert "set -euo pipefail" in body, "hook missing bash strict mode"
    assert "npm install -g openclaw" in body, "hook does not install openclaw"
    assert "openclaw.json" in body, "hook does not render the openclaw config"
    assert 'api: "openai-completions"' in body, "hook config not an OpenAI-compatible provider"
    assert "provisioning.openclaw.endpoint" in body, "hook does not read the profile endpoint"
    # Non-fatal discipline: a first-boot install that can't reach the network must skip,
    # never brick. Each skip path exits 0.
    assert body.count("exit 0") >= 3, "hook lacks the non-fatal skip paths (network/npm/node)"
    # engines band awareness (OpenClaw excludes 24.0-24.14 etc.)
    assert "node_ok" in body, "hook does not verify the Node engines band"


def test_hook_bakes_no_external_channels():
    """SDD-703 D5: preconfig points at the local model + NO baked channel credentials.
    Scan non-comment lines only — the header comment legitimately names channels as
    examples of what the operator adds LATER (not baked)."""
    active = "\n".join(
        ln for ln in HOOK.read_text(encoding="utf-8").splitlines()
        if not ln.lstrip().startswith("#")
    ).lower()
    for channel in ("whatsapp", "telegram", "discord", "slack", "imessage"):
        assert channel not in active, f"hook bakes a {channel} channel — must ship channel-free (SDD-703 D5)"


def test_hook_executable():
    import os
    assert HOOK.is_file() and os.access(HOOK, os.X_OK), "openclaw-install.sh missing or not executable"


# ---------- 6. units ----------

def test_installer_unit_first_boot_vm_tolerant():
    body = INSTALL_UNIT.read_text(encoding="utf-8")
    assert "ConditionFirstBoot=yes" in body, "installer must be first-boot only"
    # VM-tolerant: no ACTIVE ConditionVirtualization=no directive (a comment noting its
    # absence is fine — a Node daemon runs on VMs, unlike the GPU hooks).
    assert not re.search(r"(?m)^ConditionVirtualization=no", body), (
        "installer must be VM-tolerant (no active ConditionVirtualization=no directive)"
    )
    assert "network-online.target" in body, "installer must wait for network (npm/NodeSource)"
    assert "openclaw-install.sh" in body, "installer does not run the hook"
    assert "[Install]" in body, "installer has no [Install] (unreachable)"


def test_runtime_unit_installed_off_and_hardened():
    body = RUNTIME_UNIT.read_text(encoding="utf-8")
    assert "ExecStart=" in body and "openclaw gateway" in body, "runtime unit does not run the gateway"
    # Installed-off: it has [Install] (so osctl can enable) but provision-bake never enables it.
    assert "[Install]" in body, "runtime unit has no [Install]"
    # HOME relocation is what lets it stay ProtectHome=read-only while persisting state.
    assert "HOME" in body or "openclaw.env" in body, "runtime unit does not relocate HOME for its state"
    assert "ProtectSystem=strict" in body, "runtime daemon should be ProtectSystem=strict"
    assert "ReadWritePaths=/var/lib/sovereign-os/openclaw" in body, "runtime RWP not scoped to its state dir"


# ---------- 7. cli ----------

def test_osctl_openclaw_verb():
    body = OSCTL.read_text(encoding="utf-8")
    assert "cmd_openclaw()" in body, "osctl missing cmd_openclaw handler"
    assert re.search(r"^\s*openclaw\)\s+cmd_openclaw\b", body, re.M), "osctl does not dispatch the openclaw verb"
    for verb in ("openclaw status", "openclaw on", "openclaw install"):
        assert verb in body, f"osctl help does not document '{verb}'"
