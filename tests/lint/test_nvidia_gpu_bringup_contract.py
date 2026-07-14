"""NVIDIA GPU bring-up contract (SDD-701).

Two first-boot/every-boot pieces make the Blackwell GPUs usable on SAIN-01, and
each has a load-bearing property a future edit must not silently drop:

  * nvidia-driver-install.sh — installs the pinned ≥570 OPEN-kernel .run (trixie
    ships 550, pre-Blackwell). Under secure boot it MUST sign the built modules
    with the enrolled MOK (else the kernel refuses them and the GPUs stay dark),
    persist that signing for DKMS kernel-update rebuilds, and refuse a pin below
    the Blackwell 570 floor. Its unit runs at first boot, before the nouveau bind.
  * nvidia-power-limit.sh — applies each card's profile tdp_watts EVERY boot
    (nvidia-smi -pl is not persistent), matched by PCI device-id so the 5090's
    stock 575W TGP is capped to the profile's 350W and the PRO 6000 to 300W. Its
    unit is enabled at multi-user.target (not a first-boot member).

This lint pins those properties so a refactor can't regress a dark GPU or an
uncapped 575W card past CI.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
HOOKS = REPO / "scripts" / "hooks" / "post-install"
UNITS = REPO / "systemd" / "system"
INSTALL = HOOKS / "nvidia-driver-install.sh"
POWER = HOOKS / "nvidia-power-limit.sh"
INSTALL_UNIT = UNITS / "sovereign-nvidia-driver-install.service"
POWER_UNIT = UNITS / "sovereign-nvidia-power-limit.service"
PROFILE = REPO / "profiles" / "sain-01.yaml"

MIN_MAJOR = 570


def test_hooks_present_executable_and_sourced():
    for h in (INSTALL, POWER):
        assert h.is_file(), f"missing {h}"
        assert os.access(h, os.X_OK), f"{h} not executable"
        assert "lib/common.sh" in h.read_text(encoding="utf-8"), f"{h} must source common.sh"


def test_driver_install_signs_modules_for_secure_boot():
    body = INSTALL.read_text(encoding="utf-8")
    assert "--module-signing-secret-key" in body and "--module-signing-public-key" in body, (
        "driver install must MOK-sign the built modules (--module-signing-*), else "
        "secure boot rejects nvidia and the GPUs stay dark"
    )
    assert "/etc/dkms/nvidia.conf" in body and "mok_signing_key" in body, (
        "must persist the MOK signing config so a kernel-update DKMS rebuild re-signs"
    )
    assert "MOK.priv" in body and "MOK.der" in body, "must use the enrolled MOK key pair"


def test_driver_install_enforces_the_blackwell_floor():
    body = INSTALL.read_text(encoding="utf-8")
    assert f"MIN_MAJOR={MIN_MAJOR}" in body, f"must pin the ≥{MIN_MAJOR} Blackwell floor"
    # a pin below the floor must be refused (not silently installed)
    assert "pin-too-old" in body or "< ${MIN_MAJOR}" in body, (
        "must refuse a pinned driver below the Blackwell floor"
    )


def test_driver_install_serializes_initramfs():
    """SDD-998: concurrent first-boot initramfs rebuilds corrupt it — must go via boot_regen."""
    assert "boot_regen update-initramfs" in INSTALL.read_text(encoding="utf-8")


def test_power_limit_applies_per_card_caps():
    body = POWER.read_text(encoding="utf-8")
    assert "nvidia-smi" in body and "-pl" in body, "must apply nvidia-smi -pl caps"
    assert "tdp_watts" in body, "must read each GPU's tdp_watts from the profile"
    assert "pci.device_id" in body, "must match each card by PCI device-id (order-independent)"


def test_driver_install_unit_is_firstboot_before_bind():
    body = INSTALL_UNIT.read_text(encoding="utf-8")
    assert "ConditionFirstBoot=yes" in body and "ConditionVirtualization=no" in body
    assert "WantedBy=sovereign-firstboot.target" in body, "must be a first-boot target member"
    assert "Before=sovereign-nvidia-driver-bind.service" in body, (
        "the ≥570 install must run before the nouveau-blacklist bind"
    )


def test_power_limit_unit_runs_every_boot_not_firstboot():
    body = POWER_UNIT.read_text(encoding="utf-8")
    assert not re.search(r"^ConditionFirstBoot=", body, re.M), (
        "power caps reset on reboot — the unit must run EVERY boot, not only first boot"
    )
    assert "WantedBy=multi-user.target" in body
    assert "ConditionVirtualization=no" in body


def test_profile_pins_a_blackwell_capable_driver():
    prof = yaml.safe_load(PROFILE.read_text(encoding="utf-8"))
    nv = (prof.get("provisioning") or {}).get("nvidia") or {}
    ver = str(nv.get("driver_runfile_version", ""))
    assert re.match(r"^\d+", ver), "provisioning.nvidia.driver_runfile_version must be a version string"
    assert int(ver.split(".")[0]) >= MIN_MAJOR, (
        f"pinned driver {ver} < {MIN_MAJOR} — Blackwell (PRO 6000 / 5090) would not initialize"
    )
    assert nv.get("kernel_module_type") == "open", "Blackwell requires the open kernel modules"
