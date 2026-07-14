"""Inference model provisioning contract (SDD-702).

The vLLM serving tier (`sovereign-oracle-core` / `-logic-engine`, `model_serve_cli`,
`VllmBackend`) reads models from `/mnt/vault/models/<name>` and assumes `vllm` is on
PATH — but nothing installed vLLM or downloaded a real model, so a flashed box had
the serving machinery and no runtime + no weights. This lint pins the fix:

  * vLLM + huggingface_hub are declared in operator-deps [pip] (where the repo
    already said vLLM comes from);
  * the model-provision hook downloads the profile's model to /mnt/vault/models
    (where the Oracle Core reads it), is gated-token aware, and is NON-FATAL
    (a failed multi-GB pull must never brick first boot — it's resumable);
  * it wires ORACLE_MODEL at the provisioned path so the serve unit uses it;
  * the unit is a first-boot member that requires the vault mount and never
    times out the download;
  * the profile's model lands under /mnt/vault/models (not an orphan path the
    serve units can't see).
"""
from __future__ import annotations

import os
import tomllib
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
HOOK = REPO / "scripts" / "hooks" / "post-install" / "inference-model-provision.sh"
UNIT = REPO / "systemd" / "system" / "sovereign-inference-model-provision.service"
PROFILE = REPO / "profiles" / "sain-01.yaml"
OPDEPS = REPO / "config" / "operator-deps.toml.example"

VAULT_MODELS = "/mnt/vault/models"


def test_operator_deps_declares_vllm_and_hf():
    deps = tomllib.loads(OPDEPS.read_text(encoding="utf-8"))
    pip = set(deps.get("pip", {}).get("install", []))
    assert "vllm" in pip, "vLLM must be declared in operator-deps [pip] (the serve layer assumes it on PATH)"
    assert any(p.replace("-", "_") == "huggingface_hub" for p in pip), (
        "huggingface_hub must be declared (huggingface-cli download for the model pull)"
    )


def test_hook_present_executable_sourced():
    assert HOOK.is_file() and os.access(HOOK, os.X_OK), f"{HOOK} missing or not executable"
    assert "lib/common.sh" in HOOK.read_text(encoding="utf-8")


def test_hook_downloads_to_vault_models_and_wires_oracle():
    body = HOOK.read_text(encoding="utf-8")
    assert "huggingface-cli" in body, "must use huggingface-cli download (sharded + resumable + gated)"
    assert "ORACLE_MODEL" in body and "inference-oracle-core.env" in body, (
        "must point the Oracle Core serve unit at the provisioned model"
    )
    assert "SOVEREIGN_OS_HF_TOKEN" in body, "must be gated-token aware"


def test_hook_is_non_fatal_on_missing_prereqs():
    """A failed multi-GB pull (no CLI / no token / no space / download error) must
    skip cleanly, never brick first boot — each path emits a metric + exits 0."""
    body = HOOK.read_text(encoding="utf-8")
    for marker in ("no-hf-cli", "no-space", "download-failed"):
        assert marker in body, f"missing graceful-skip path: {marker}"


def test_unit_is_firstboot_member_requiring_the_vault():
    body = UNIT.read_text(encoding="utf-8")
    assert "ConditionFirstBoot=yes" in body and "ConditionVirtualization=no" in body
    assert "WantedBy=sovereign-firstboot.target" in body, "must be a first-boot target member"
    assert f"RequiresMountsFor={VAULT_MODELS}" in body, "must require the ZFS vault mount before the pull"
    assert "TimeoutStartSec=0" in body, "a multi-GB download must not be timed out"


def test_profile_model_lands_where_the_serve_units_read():
    prof = yaml.safe_load(PROFILE.read_text(encoding="utf-8"))
    model = (prof.get("provisioning") or {}).get("model") or {}
    local_dir = model.get("local_dir", "")
    assert local_dir.startswith(VAULT_MODELS + "/"), (
        f"provisioning.model.local_dir must be under {VAULT_MODELS} (where the Oracle Core reads); got {local_dir!r}"
    )
    assert model.get("repo"), "provisioning.model.repo must name the model to download"
