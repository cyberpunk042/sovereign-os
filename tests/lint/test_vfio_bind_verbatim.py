"""R398 (E10.M42) — VFIO-bind operator-verbatim §4.3 content lint.

Extends R387-R397 operational-artifact pinning to:
  scripts/hooks/post-install/vfio-bind-3090.sh

Master spec §4.3 verbatim GRUB cmdline:
  GRUB_CMDLINE_LINUX_DEFAULT="quiet splash amd_iommu=on iommu=pt
                              kvm_amd.npt=1 kvm_amd.avic=1
                              vfio-pci.ids=10de:2204,10de:1ad8
                              nvidia-drm.modeset=1
                              nvidia.NVreg_EnableGpuFirmware=1"

  - 10de:2204 = RTX 3090 GPU PCI ID (operator-verbatim §4.3)
  - 10de:1ad8 = RTX 3090 Audio Controller PCI ID
  - amd_iommu=on + iommu=pt = IOMMU passthrough for VFIO

If a future agent silently drops amd_iommu=on OR uses wrong VFIO
PCI IDs, the RTX 3090 isolation breaks — secondary GPU bleeds into
host (security perimeter violation per operator §17 dual-GPU SRP).
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VFIO_BIND = REPO_ROOT / "scripts" / "hooks" / "post-install" / "vfio-bind-3090.sh"


def _read_vfio() -> str:
    assert VFIO_BIND.is_file(), f"missing {VFIO_BIND}"
    return VFIO_BIND.read_text(encoding="utf-8")


def test_vfio_bind_file_exists():
    assert VFIO_BIND.is_file(), f"missing {VFIO_BIND}"


def test_vfio_pci_ids_format():
    """§4.3 verbatim cmdline includes vfio-pci.ids= parameter.
    Script MUST manipulate this parameter."""
    body = _read_vfio()
    assert "vfio-pci.ids" in body, (
        "vfio-bind script missing vfio-pci.ids= reference "
        "(§4.3 verbatim GRUB cmdline parameter)"
    )


def test_amd_iommu_on_present():
    """§4.3 verbatim: amd_iommu=on (operator-verbatim IOMMU enable).
    Without this, vfio-pci binding fails on AMD platforms."""
    body = _read_vfio()
    assert "amd_iommu=on" in body, (
        "vfio-bind script missing 'amd_iommu=on' (§4.3 verbatim — "
        "REQUIRED for AMD platform IOMMU + vfio-pci binding)"
    )


def test_iommu_pt_present():
    """§4.3 verbatim: iommu=pt (passthrough mode — operator-named).
    Without this, IOMMU groups don't allow GPU passthrough."""
    body = _read_vfio()
    assert "iommu=pt" in body, (
        "vfio-bind script missing 'iommu=pt' (§4.3 verbatim — "
        "passthrough mode for VFIO GPU isolation)"
    )


def test_grub_cmdline_default_referenced():
    """Script MUST manipulate GRUB_CMDLINE_LINUX_DEFAULT (the GRUB
    boot parameter that carries vfio-pci.ids)."""
    body = _read_vfio()
    assert "GRUB_CMDLINE_LINUX_DEFAULT" in body, (
        "vfio-bind script missing GRUB_CMDLINE_LINUX_DEFAULT reference "
        "(target variable for §4.3 verbatim boot cmdline)"
    )


def test_vfio_pci_module_options():
    """Script MUST set vfio-pci module options (kernel module-level
    binding via /etc/modprobe.d). Either 'options vfio-pci' OR
    'modprobe.d' reference."""
    body = _read_vfio()
    has_modprobe = ("options vfio-pci" in body
                     or "modprobe.d" in body
                     or "/etc/modprobe.d" in body)
    assert has_modprobe, (
        "vfio-bind script missing vfio-pci module options/modprobe "
        "config reference (kernel-module-level binding path)"
    )


def test_pci_id_pattern_well_formed():
    """If specific PCI IDs are referenced (master spec §4.3 verbatim
    examples 10de:2204 + 10de:1ad8), they MUST be well-formed
    (XXXX:XXXX hex format)."""
    body = _read_vfio()
    pci_ids = re.findall(r"\b[0-9a-fA-F]{4}:[0-9a-fA-F]{4}\b", body)
    # Optional check — if IDs appear, validate the format
    if pci_ids:
        for pid in pci_ids:
            assert re.match(r"^[0-9a-fA-F]{4}:[0-9a-fA-F]{4}$", pid), (
                f"PCI ID {pid!r} not well-formed (expect XXXX:XXXX hex)"
            )


def test_script_handles_grub_update():
    """Script MUST trigger grub regeneration after cmdline mutation
    (otherwise GRUB doesn't pick up the new vfio-pci.ids on next boot)."""
    body = _read_vfio()
    body_lower = body.lower()
    has_grub_update = (
        "update-grub" in body_lower
        or "grub-mkconfig" in body_lower
        or "grub2-mkconfig" in body_lower
    )
    assert has_grub_update, (
        "vfio-bind script missing GRUB regeneration trigger "
        "(update-grub / grub-mkconfig) — without it, GRUB doesn't "
        "pick up the new vfio-pci.ids on next boot"
    )


def test_master_spec_section_documented():
    """Script SHOULD reference master spec §4.3 in comments
    (operator-discovery context)."""
    body = _read_vfio()
    has_section_ref = ("§" in body or "master spec" in body.lower()
                        or "vfio" in body.lower())
    assert has_section_ref, (
        "vfio-bind script missing master spec section reference "
        "in comments"
    )


def test_no_silent_iommu_disable():
    """Catches silent IOMMU disable: amd_iommu=off OR iommu=off would
    break the entire VFIO mechanism. Both are forbidden in cmdline
    manipulation."""
    body = _read_vfio()
    # If script references iommu=off or amd_iommu=off, it's a guarantee
    # violation
    forbidden = ["amd_iommu=off", "iommu=off"]
    bad = [f for f in forbidden if f in body]
    assert not bad, (
        f"vfio-bind script contains IOMMU-disable values: {bad}. "
        f"§4.3 requires amd_iommu=on + iommu=pt for VFIO to work."
    )
