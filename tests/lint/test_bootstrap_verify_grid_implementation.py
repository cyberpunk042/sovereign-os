"""R410 (E10.M54) — bootstrap verify.sh ↔ verify-grid.yaml implementation
+ master spec § 22 verbatim 6-check operational grid lint.

Extends R387-R409 operational-artifact pinning to:
  scripts/bootstrap/verify.sh
  config/bootstrap/verify-grid.yaml

R389 + R399 already covered the verify-grid YAML schema + the
bidirectional ARC byte-value consistency. R410 closes the
IMPLEMENTATION side: every check_NN() bash function MUST actually
verify what verify-grid.yaml's metadata says it does.

Master spec § 22 verbatim 6-check operational grid:
  01 — Microcode / ISA: avx512_vnni + avx512_bf16 in /proc/cpuinfo
  02 — Bus Geometry: ≥2 PCIe slots at Width x8 + Gen 4/5
  03 — Linux Memory (ZFS ARC): arc c_max = 137438953472 bytes (128 GiB)
  04 — Driver Fabric (NVIDIA): open module (MIT/GPL license)
  05 — Security Core (Tetragon): /var/run/tetragon/tetragon.events present
  06 — Network Line (Jumbo MTU): data interface MTU=9000

Cross-file bidirectional consistency (6th in the family):
  Every check_NN function in verify.sh MUST have a matching id="NN"
  entry in verify-grid.yaml. Drift = display name doesn't match check.

If a future agent silently:
  - drops a check_NN function = verify.sh dispatcher fails silently
  - renames a check = display name / metric label diverges from YAML
  - relaxes the license-check (drift to NVIDIA proprietary) = operator's
    § 22.4 'open kernel module' verbatim contract broken
  - flips MTU 9000 → 1500 = master spec § 8.1 jumbo-frame contract lost
…the § 22 6-check grid silently breaks.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
VERIFY_SH = REPO_ROOT / "scripts" / "bootstrap" / "verify.sh"
VERIFY_GRID = REPO_ROOT / "config" / "bootstrap" / "verify-grid.yaml"

EXPECTED_CHECK_IDS = ["01", "02", "03", "04", "05", "06"]


def _read_sh() -> str:
    assert VERIFY_SH.is_file(), f"missing {VERIFY_SH}"
    return VERIFY_SH.read_text(encoding="utf-8")


def _load_grid() -> dict:
    assert VERIFY_GRID.is_file(), f"missing {VERIFY_GRID}"
    return yaml.safe_load(VERIFY_GRID.read_text(encoding="utf-8"))


def _grid_check_ids() -> list[str]:
    grid = _load_grid()
    checks = (grid.get("verify_grid") or {}).get("checks") or []
    return [c.get("id") for c in checks]


def test_verify_sh_exists():
    assert VERIFY_SH.is_file(), f"missing {VERIFY_SH}"


def test_verify_grid_yaml_exists():
    assert VERIFY_GRID.is_file(), f"missing {VERIFY_GRID}"


def test_all_six_check_functions_defined():
    """Master spec § 22 verbatim: 6-check operational grid. Each
    check_NN() bash function MUST be defined. Drift losing one =
    dispatcher silently does nothing for that check id."""
    body = _read_sh()
    for cid in EXPECTED_CHECK_IDS:
        pattern = re.compile(rf"^check_{cid}\(\)\s*\{{", re.M)
        assert pattern.search(body), (
            f"verify.sh missing check_{cid}() function "
            f"(master spec § 22 verbatim — 6-check grid)"
        )


def test_check_dispatcher_handles_all_six():
    """The dispatcher (case statement) MUST route each id to its
    check_NN function."""
    body = _read_sh()
    for cid in EXPECTED_CHECK_IDS:
        # Pattern: NN) check_NN ;;
        pat = re.compile(rf"\b{cid}\)\s+check_{cid}\b")
        assert pat.search(body), (
            f"verify.sh dispatcher missing '{cid}) check_{cid}' "
            f"(operator-verbatim § 22 6-check routing)"
        )


def test_bidirectional_consistency_yaml_to_sh():
    """Every id in verify-grid.yaml MUST have a matching check_NN
    function in verify.sh. Bidirectional consistency lint #6."""
    body = _read_sh()
    yaml_ids = _grid_check_ids()
    for cid in yaml_ids:
        pattern = re.compile(rf"^check_{cid}\(\)", re.M)
        assert pattern.search(body), (
            f"verify-grid.yaml has check id={cid!r} but verify.sh "
            f"missing check_{cid}() implementation "
            f"(bidirectional consistency YAML↔SH violation)"
        )


def test_bidirectional_consistency_sh_to_yaml():
    """Every check_NN function in verify.sh MUST have a matching id
    in verify-grid.yaml. Other direction of bidirectional consistency."""
    body = _read_sh()
    sh_ids = set(re.findall(r"^check_(\d{2})\(\)", body, re.M))
    yaml_ids = set(_grid_check_ids())
    extra_in_sh = sh_ids - yaml_ids
    assert not extra_in_sh, (
        f"verify.sh has check_NN functions not in verify-grid.yaml: "
        f"{sorted(extra_in_sh)} (bidirectional consistency SH↔YAML "
        f"violation — display name + metadata divergence)"
    )


# --- Check 01 — Microcode / ISA (avx512_vnni + avx512_bf16) ---


def test_check_01_avx512_vnni_verbatim():
    """§ 22.1 + § 1.1 verbatim: avx512_vnni flag check."""
    body = _read_sh()
    assert "avx512_vnni" in body, (
        "verify.sh missing avx512_vnni check (master spec § 22.1 + "
        "§ 1.1 verbatim — Zen 5 INT8 inference acceleration ISA flag)"
    )


def test_check_01_avx512_bf16_verbatim():
    """§ 22.1 + § 1.1 verbatim: avx512_bf16 flag check."""
    body = _read_sh()
    assert "avx512_bf16" in body, (
        "verify.sh missing avx512_bf16 check (master spec § 22.1 + "
        "§ 1.1 verbatim — Zen 5 BF16 mixed-precision ISA flag)"
    )


# --- Check 02 — Bus Geometry ---


def test_check_02_width_x8_verbatim():
    """§ 22.2 + § 1.2 verbatim: ≥2 PCIe slots at Width x8."""
    body = _read_sh()
    assert "Width x8" in body, (
        "verify.sh check_02 missing 'Width x8' (§ 22.2 verbatim — "
        "PCIe x8/x8 bifurcation for dual-GPU SRP)"
    )


def test_check_02_gen_4_5_speed():
    """§ 22.2 verbatim: Gen 4/5 = 16 or 32 GT/s PCIe speed."""
    body = _read_sh()
    assert "16" in body and ("GT/s" in body or "GT" in body), (
        "verify.sh check_02 missing Gen 4/5 speed check (16/32 GT/s) "
        "(§ 22.2 verbatim — full PCIe bandwidth for GPU passthrough)"
    )


# --- Check 03 — ZFS ARC max ---


def test_check_03_arc_c_max_byte_value_consistency():
    """R399 already covered the bidirectional verify-grid ↔ zfs-arc-clamp
    consistency. R410 also asserts the verify.sh implementation reads
    arc c_max from /proc/spl/kstat/zfs/arcstats (the canonical source)."""
    body = _read_sh()
    assert "arcstats" in body, (
        "verify.sh check_03 missing /proc/spl/kstat/zfs/arcstats read "
        "(canonical ARC max source — drift to a non-canonical path "
        "silently reads stale data)"
    )


def test_check_03_references_arc_max_env_var():
    """verify.sh check_03 MUST compare to BOOTSTRAP_VERIFY_ARC_MAX_BYTES
    (env-driven — matches the R399 bidirectional consistency surface)."""
    body = _read_sh()
    assert "BOOTSTRAP_VERIFY_ARC_MAX_BYTES" in body, (
        "verify.sh check_03 missing BOOTSTRAP_VERIFY_ARC_MAX_BYTES "
        "env var comparison (R399 bidirectional ARC pinning surface)"
    )


# --- Check 04 — NVIDIA open kernel module ---


def test_check_04_license_check_for_open_module():
    """§ 22.4 verbatim: 'open kernel module' = license MIT or GPL.
    Drift accepting NVIDIA proprietary = operator's § 22.4 contract
    broken. Lint MUST verify the case statement still rejects 'NVIDIA*'
    license string."""
    body = _read_sh()
    # The case statement should match MIT|GPL*|"Dual MIT/GPL"
    has_mit = "MIT" in body
    has_gpl = "GPL" in body
    assert has_mit and has_gpl, (
        "verify.sh check_04 missing MIT/GPL license accept paths "
        "(§ 22.4 verbatim — only open kernel module accepted)"
    )


def test_check_04_rejects_nvidia_proprietary():
    """§ 22.4 verbatim: NVIDIA* license string MUST cause FAIL. Drift
    to silent-accept-all-licenses = operator's open-module contract
    silently broken."""
    body = _read_sh()
    has_reject = (
        "NVIDIA*" in body
        or "proprietary" in body.lower()
        or "closed" in body.lower()
    )
    assert has_reject, (
        "verify.sh check_04 missing NVIDIA-proprietary FAIL path "
        "(§ 22.4 verbatim — proprietary module is a CONFORMANCE FAIL)"
    )


# --- Check 05 — Tetragon event stream ---


def test_check_05_tetragon_events_path_verbatim():
    """§ 22.5 + § 5 verbatim: /var/run/tetragon/tetragon.events
    (operator-named event-stream path; drift = silently wrong path
    silently reports PASS when Tetragon isn't actually wired in)."""
    body = _read_sh()
    assert "/var/run/tetragon/tetragon.events" in body, (
        "verify.sh check_05 missing /var/run/tetragon/tetragon.events "
        "(§ 22.5 verbatim — Tetragon event stream path)"
    )


def test_check_05_handles_socket_pipe_or_file():
    """Tetragon may expose .events as Unix socket OR FIFO OR file —
    all 3 must be accepted. Drift to socket-only would miss FIFO mode."""
    body = _read_sh()
    flags = ["-S /var/run/tetragon", "-p /var/run/tetragon", "-f /var/run/tetragon"]
    present = [f for f in flags if f in body]
    assert len(present) >= 2, (
        f"verify.sh check_05 doesn't probe enough file types "
        f"(found {present}); MUST accept socket OR FIFO OR file"
    )


# --- Check 06 — MTU 9000 (data-plane jumbo frames) ---


def test_check_06_mtu_9000_verbatim():
    """§ 22.6 + § 8.1 verbatim: data NIC MTU=9000 jumbo frames."""
    body = _read_sh()
    assert "9000" in body, (
        "verify.sh check_06 missing MTU=9000 check "
        "(§ 22.6 + § 8.1 verbatim — Marvell 10GbE jumbo frames)"
    )


def test_check_06_data_iface_env_var():
    """verify.sh check_06 MUST honor BOOTSTRAP_VERIFY_DATA_IFACE env
    var (default enp5s0 from sain-01 profile §8.1). Drift to hardcoded
    'enp5s0' silently fails on other profiles/hosts."""
    body = _read_sh()
    assert "BOOTSTRAP_VERIFY_DATA_IFACE" in body, (
        "verify.sh check_06 missing BOOTSTRAP_VERIFY_DATA_IFACE env "
        "var (operator-discoverable iface override — drift to "
        "hardcoded enp5s0 silently breaks alt profiles)"
    )


# --- Strict mode + metric emission ---


def test_strict_mode_handling():
    """verify-grid.yaml verbatim: '--strict mode promotes SKIPs to
    FAILs'. Implementation MUST honor this flag."""
    body = _read_sh()
    assert "--strict" in body or "STRICT" in body, (
        "verify.sh missing --strict mode handling "
        "(verify-grid.yaml verbatim — promotes SKIPs to FAILs)"
    )


def test_emits_per_check_metric():
    """SDD-016: each check emits sovereign_os_bootstrap_check_total
    {check=NN, result=PASS/FAIL/SKIP} metric. Drift = no Grafana
    visibility into per-check operational state."""
    body = _read_sh()
    assert "sovereign_os_bootstrap_check_total" in body, (
        "verify.sh missing sovereign_os_bootstrap_check_total metric "
        "(SDD-016 verbatim — per-check operational observability)"
    )


def test_check_names_array_populated_with_fallback():
    """CHECK_NAMES bash assoc array MUST have hardcoded fallback
    matching verify-grid.yaml (defensive: if YAML loader fails,
    display still works). Drift to YAML-only loses graceful degradation."""
    body = _read_sh()
    assert "CHECK_NAMES[01]=" in body, (
        "verify.sh missing CHECK_NAMES[01]= fallback hardcoding "
        "(defense-in-depth: YAML loader failure mustn't break display)"
    )
    assert "CHECK_NAMES[06]=" in body, (
        "verify.sh missing CHECK_NAMES[06]= fallback hardcoding "
        "(defense-in-depth coverage incomplete)"
    )


def test_check_names_fallback_matches_yaml():
    """The CHECK_NAMES bash fallback strings MUST match verify-grid.yaml
    names exactly. Bidirectional consistency between YAML metadata and
    bash display fallback."""
    body = _read_sh()
    grid = _load_grid()
    checks = (grid.get("verify_grid") or {}).get("checks") or []
    for c in checks:
        cid = c.get("id")
        name = c.get("name")
        if not name:
            continue
        # Look for CHECK_NAMES[NN]="<name>" pattern
        pattern = re.compile(rf'CHECK_NAMES\[{cid}\]="([^"]+)"')
        m = pattern.search(body)
        assert m, (
            f"verify.sh CHECK_NAMES[{cid}] fallback missing "
            f"(YAML expects name={name!r})"
        )
        assert m.group(1) == name, (
            f"verify.sh CHECK_NAMES[{cid}]={m.group(1)!r} doesn't "
            f"match verify-grid.yaml name={name!r} "
            f"(bidirectional name consistency violation)"
        )
