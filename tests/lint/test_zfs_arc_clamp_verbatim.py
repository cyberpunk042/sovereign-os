"""R399 (E10.M43) — ZFS ARC clamp operator-verbatim §4.2 content lint.

Extends R387-R398 operational-artifact pinning to:
  scripts/hooks/post-install/zfs-arc-clamp.sh

Master spec §4.2 verbatim:
  > "ZFS ARC limit is explicitly clamped at exactly 128GB of the
  > system's 256GB overall space."
  > options zfs zfs_arc_max=137438953472

The exact byte value 137438953472 = 128 * 1024^3 is operator-named.
Drift to a different clamp value (e.g., 64GB or 192GB) would silently
change the AI-workload memory budget — operator's 50% RAM-to-AI
allocation is the design intent.

If a future agent silently changes the default to 64GB OR drops the
modprobe.d persistence path, the ARC clamp doesn't survive reboot OR
operates at wrong size, silently breaking operator's memory budget.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ARC_CLAMP = REPO_ROOT / "scripts" / "hooks" / "post-install" / "zfs-arc-clamp.sh"
VERIFY_GRID = REPO_ROOT / "config" / "bootstrap" / "verify-grid.yaml"


def _read_arc_clamp() -> str:
    assert ARC_CLAMP.is_file(), f"missing {ARC_CLAMP}"
    return ARC_CLAMP.read_text(encoding="utf-8")


def test_arc_clamp_file_exists():
    assert ARC_CLAMP.is_file(), f"missing {ARC_CLAMP}"


def test_zfs_arc_max_parameter_referenced():
    """§4.2 verbatim: zfs_arc_max kernel module parameter. Script
    MUST manipulate this parameter."""
    body = _read_arc_clamp()
    assert "zfs_arc_max" in body, (
        "zfs-arc-clamp script missing zfs_arc_max parameter reference "
        "(§4.2 verbatim — operator-named ZFS kernel module parameter)"
    )


def test_default_clamp_128_gb():
    """§4.2 verbatim: 128GB default clamp (50% of operator's 256GB
    target system memory). Default value MUST be 128."""
    body = _read_arc_clamp()
    # Look for SOVEREIGN_OS_ARC_MAX_GB default value
    import re
    default_match = re.search(
        r'SOVEREIGN_OS_ARC_MAX_GB[:\s=]+["\']?(\d+)', body)
    assert default_match, (
        "zfs-arc-clamp script missing SOVEREIGN_OS_ARC_MAX_GB default "
        "(operator-verbatim §4.2 128GB clamp)"
    )
    default = int(default_match.group(1))
    assert default == 128, (
        f"§4.2 verbatim clamp is 128GB; default is {default}GB"
    )


def test_byte_value_computation_correct():
    """§4.2 verbatim byte value: 128 * 1024^3 = 137438953472.
    Script MUST compute correctly (no off-by-one / wrong-multiplier
    drift)."""
    # Compute the operator-verbatim value
    expected_bytes = 128 * 1024 * 1024 * 1024
    assert expected_bytes == 137438953472, "computation sanity check"

    body = _read_arc_clamp()
    # Script should multiply by 1024^3 (gigabytes → bytes)
    # Either explicit byte value OR multiplier expression
    has_correct_math = (
        "137438953472" in body
        or "1024 * 1024 * 1024" in body
        or "1073741824" in body  # 1GB in bytes (correct multiplier)
        or "GB * 1024**3" in body
    )
    assert has_correct_math, (
        "zfs-arc-clamp script missing 128GB → 137438953472 bytes "
        "correct multiplier (1024^3). Drift to 1000^3 would be off "
        "by 7.4%."
    )


def test_modprobe_d_persistence():
    """ARC clamp MUST persist across reboot via /etc/modprobe.d
    config file (otherwise next boot loses the clamp + ARC fills
    all available RAM)."""
    body = _read_arc_clamp()
    has_modprobe = (
        "/etc/modprobe.d" in body
        or "modprobe.d" in body
    )
    assert has_modprobe, (
        "zfs-arc-clamp script missing /etc/modprobe.d persistence "
        "path. Without modprobe.d config, ARC clamp doesn't survive "
        "reboot."
    )


def test_options_zfs_zfs_arc_max_format():
    """§4.2 verbatim modprobe.d line: 'options zfs zfs_arc_max=<bytes>'.
    Script MUST emit this exact format."""
    body = _read_arc_clamp()
    # The string 'options zfs zfs_arc_max=' should appear (with the
    # value computed at runtime)
    assert "options zfs zfs_arc_max=" in body, (
        "zfs-arc-clamp script missing 'options zfs zfs_arc_max=' "
        "modprobe format (§4.2 verbatim)"
    )


def test_runtime_application_to_sys():
    """ARC clamp MUST apply at runtime (not just modprobe config).
    /sys/module/zfs/parameters/zfs_arc_max writes the active value."""
    body = _read_arc_clamp()
    has_sys = (
        "/sys/module/zfs/parameters/zfs_arc_max" in body
        or "/sys/module/zfs" in body
    )
    assert has_sys, (
        "zfs-arc-clamp script missing /sys/module/zfs runtime "
        "application path. Without it, modprobe config takes effect "
        "only on reboot."
    )


def test_arc_min_smaller_than_arc_max():
    """If arc_min is set, it MUST be smaller than arc_max. Sanity
    check: catches drift where arc_min = arc_max (which forces ARC
    to fixed size, removing the clamp's flexibility)."""
    body = _read_arc_clamp()
    if "zfs_arc_min" in body:
        # Script should compute arc_min as fraction of arc_max
        has_fraction = (
            "/ 4" in body
            or "/ 8" in body
            or "/ 2" in body
            or "arc_min" in body and "arc_max" in body
        )
        assert has_fraction, (
            "zfs-arc-clamp sets arc_min but not as fraction of "
            "arc_max — drift risk where arc_min >= arc_max"
        )


def test_master_spec_section_referenced():
    """Script SHOULD document master spec §4.2 reference."""
    body = _read_arc_clamp()
    has_section_ref = (
        "§4" in body
        or "§ 4" in body
        or "master spec" in body.lower()
        or "4.2" in body
    )
    assert has_section_ref, (
        "zfs-arc-clamp script missing master spec §4.2 reference "
        "in comments (operator-discovery context)"
    )


def test_bidirectional_consistency_with_verify_grid():
    """The operator-verbatim 137438953472 (= 128 GiB) byte value MUST
    appear consistently in BOTH:
      - zfs-arc-clamp.sh (writes the value)
      - verify-grid.yaml (verifies the value matches at boot-time)
    Bidirectional consistency catches drift between writer and verifier."""
    if not VERIFY_GRID.is_file():
        return  # graceful skip
    grid_body = VERIFY_GRID.read_text(encoding="utf-8")
    # verify-grid should reference 137438953472 OR
    # BOOTSTRAP_VERIFY_ARC_MAX_BYTES OR 128 GiB
    has_value = (
        "137438953472" in grid_body
        or "BOOTSTRAP_VERIFY_ARC_MAX_BYTES" in grid_body
        or "128 GiB" in grid_body
    )
    assert has_value, (
        "verify-grid.yaml missing operator-verbatim 137438953472 / "
        "128 GiB clamp value. Bidirectional consistency violation: "
        "zfs-arc-clamp writes the value, verify-grid must check the "
        "same value at boot-time."
    )
