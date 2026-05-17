"""Layer 1 lint — every systemd service unit MUST declare defense-in-depth
sandbox flags (ProtectSystem, NoNewPrivileges, PrivateTmp) or carry an
explicit '# HARDENING-WAIVER: <reason>' comment.

R160 extension: long-running services (Type=simple/notify/exec) must
carry the full hardening set — ProtectHome, ProtectKernelTunables,
ProtectControlGroups, LockPersonality, RestrictRealtime — since they
stay resident and expose ongoing attack surface.

Catches regressions where a new service unit lands without sandboxing.
"""

from __future__ import annotations

import pathlib

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
UNIT_DIR = REPO_ROOT / "systemd" / "system"

REQUIRED_KEYS = ("ProtectSystem", "NoNewPrivileges", "PrivateTmp")

# R160 — long-running services additionally require these. Each is
# satisfied either by a literal `Key=true` (case-insensitive) OR by
# `DynamicUser=true` for the keys it implies (ProtectHome).
LONG_RUNNING_KEYS = (
    "ProtectKernelTunables",
    "ProtectControlGroups",
    "LockPersonality",
    "RestrictRealtime",
)


def _service_units() -> list[pathlib.Path]:
    return sorted(UNIT_DIR.glob("*.service"))


def _parse_service(path: pathlib.Path) -> dict:
    """Returns Service-section key→value dict (later assignments win,
    case-preserving keys)."""
    section = ""
    out: dict = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            continue
        if "=" not in line or section != "Service":
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def _is_long_running(svc: dict) -> bool:
    return svc.get("Type", "simple").lower() in ("simple", "notify", "exec")


def _long_running_services() -> list[pathlib.Path]:
    return [p for p in _service_units() if _is_long_running(_parse_service(p))]


def test_unit_dir_exists():
    assert UNIT_DIR.is_dir(), f"systemd unit dir missing: {UNIT_DIR}"


def test_service_units_present():
    units = _service_units()
    assert len(units) >= 10, f"expected ≥10 service units, found {len(units)}"


@pytest.mark.parametrize("unit", _service_units(), ids=lambda p: p.name)
def test_unit_is_hardened(unit: pathlib.Path):
    """Every service unit declares the three sandbox keys OR has a waiver."""
    text = unit.read_text()

    if "# HARDENING-WAIVER:" in text:
        # Explicit waiver — accept (reason recorded in the unit file)
        return

    missing = [k for k in REQUIRED_KEYS if f"{k}=" not in text]
    assert not missing, (
        f"{unit.name} missing sandbox keys: {missing}. "
        f"Add them under [Service] or add a '# HARDENING-WAIVER: <reason>' "
        f"comment if the unit legitimately cannot be sandboxed."
    )


# ---------- R160 extended hardening for long-running services ----------

def test_at_least_four_long_running_services_known():
    """Sanity: the 4 inference services are correctly detected as
    long-running by Type heuristics."""
    names = {p.name for p in _long_running_services()}
    expected = {
        "sovereign-pulse.service",
        "sovereign-logic-engine.service",
        "sovereign-oracle-core.service",
        "sovereign-router.service",
    }
    missing = expected - names
    assert not missing, f"missing long-running services: {missing}"


@pytest.mark.parametrize(
    "unit", _long_running_services(), ids=lambda p: p.name
)
def test_long_running_has_protect_home(unit: pathlib.Path):
    text = unit.read_text()
    if "# HARDENING-WAIVER:" in text:
        return
    svc = _parse_service(unit)
    if svc.get("DynamicUser", "").lower() == "true":
        return  # DynamicUser implies ProtectHome
    val = svc.get("ProtectHome", "").lower()
    assert val in ("true", "read-only"), (
        f"{unit.name} long-running missing ProtectHome=true|read-only "
        f"(got '{val}')"
    )


@pytest.mark.parametrize(
    "unit", _long_running_services(), ids=lambda p: p.name
)
def test_long_running_extended_hardening(unit: pathlib.Path):
    text = unit.read_text()
    if "# HARDENING-WAIVER:" in text:
        return
    svc = _parse_service(unit)
    missing = []
    for k in LONG_RUNNING_KEYS:
        v = svc.get(k, "").lower()
        if v != "true":
            missing.append(k)
    assert not missing, (
        f"{unit.name} long-running missing extended hardening: {missing}"
    )


# ---------- R171 defense-in-depth baseline (every service) ----------
#
# R171 extends the per-unit floor: regardless of long/short running,
# every service unit must declare these directives (or carry the
# global # HARDENING-WAIVER: comment). They're the directives that
# are uniformly safe — they don't block any current ExecStart and
# tighten the kernel-attack surface uniformly across the fleet.
#
# Per-key waiver: append "  # HARDENING-WAIVER-KEY: <reason>" on
# the SAME line as the assignment to opt out of a single key without
# disabling the whole-service waiver. Empty value waiver (`Key=`)
# is rejected.

R171_BASELINE = (
    "ProtectHome",
    "ProtectKernelTunables",
    "ProtectKernelModules",
    "ProtectControlGroups",
    "ProtectClock",
    "ProtectHostname",
    "RestrictRealtime",
    "RestrictSUIDSGID",
    "RestrictNamespaces",
    "LockPersonality",
)


@pytest.mark.parametrize("unit", _service_units(), ids=lambda p: p.name)
def test_r171_defense_in_depth_baseline(unit: pathlib.Path):
    """R171: every service unit declares the 10-directive defense-in-
    depth baseline (or carries an explicit waiver)."""
    text = unit.read_text()
    if "# HARDENING-WAIVER:" in text:
        return
    svc = _parse_service(unit)
    missing = []
    for k in R171_BASELINE:
        raw_val = svc.get(k, "")
        # _parse_service preserves inline-comment tails; split them off.
        val = raw_val.split("#", 1)[0].strip().lower()
        # RestrictNamespaces: long-running services may legitimately
        # set =false when running container runtimes that need unshare
        # (logic-engine + oracle-core). Accept "false" only when an
        # inline rationale comment appears on the assignment line.
        if k == "RestrictNamespaces" and val == "false":
            if "#" in raw_val:
                continue
            missing.append(f"{k}=false (no rationale comment)")
            continue
        # ProtectHome: read-only is an acceptable degraded mode for
        # services that need to inspect $HOME but never write to it.
        if k == "ProtectHome" and val in ("true", "read-only", "tmpfs"):
            continue
        if val != "true":
            missing.append(k)
    assert not missing, (
        f"{unit.name} missing R171 baseline: {missing}. "
        f"Add the directives under [Service], or add a "
        f"'# HARDENING-WAIVER: <reason>' comment to the unit."
    )


# ---------- R346 inference-service stricter posture (SDD-036) -------
#
# The 4 inference daemons accept attacker-controlled prompt text and
# parse model files; they deserve harder defenses than ambient services.
# Required directives (each may be =false with an inline-comment rationale
# on the SAME line — codegen-needs-W^X is a real engineering tradeoff):
#   - MemoryDenyWriteExecute    (defeats most ROP→shellcode chains)
#   - RestrictAddressFamilies   (cuts the AF reachable from a compromised
#                                worker — e.g. AF_PACKET, AF_VSOCK).
#
# Inline-comment waiver pattern (mirrors RestrictNamespaces=false):
#   MemoryDenyWriteExecute=false  # vLLM JIT-compiles CUDA kernels
#   RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6  # narrower set OK
#
# An empty waiver value (e.g. `MemoryDenyWriteExecute=`) is rejected.

INFERENCE_SERVICES = {
    "sovereign-pulse.service",
    "sovereign-logic-engine.service",
    "sovereign-oracle-core.service",
    "sovereign-router.service",
}

INFERENCE_HARDER_KEYS = (
    "MemoryDenyWriteExecute",
    "RestrictAddressFamilies",
)


def _inference_units() -> list[pathlib.Path]:
    return [p for p in _service_units() if p.name in INFERENCE_SERVICES]


def test_inference_units_present():
    found = {p.name for p in _inference_units()}
    missing = INFERENCE_SERVICES - found
    assert not missing, (
        f"R346: expected inference service units missing: {missing}"
    )


@pytest.mark.parametrize(
    "unit", _inference_units(), ids=lambda p: p.name
)
def test_inference_service_harder_posture(unit: pathlib.Path):
    """R346/SDD-036: the 4 inference daemons enforce stricter posture
    (MemoryDenyWriteExecute + RestrictAddressFamilies). Each may be
    =false ONLY with an inline-comment rationale."""
    text = unit.read_text()
    if "# HARDENING-WAIVER:" in text:
        return
    # Build (key → (raw_value, has_inline_comment)) for [Service] section.
    parsed: dict[str, tuple[str, bool]] = {}
    section = ""
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
            continue
        if "=" not in stripped or section != "Service":
            continue
        k, v = stripped.split("=", 1)
        parsed[k.strip()] = (v, "#" in v)

    missing = []
    for key in INFERENCE_HARDER_KEYS:
        if key not in parsed:
            missing.append(f"{key} (absent)")
            continue
        raw_val, has_comment = parsed[key]
        val = raw_val.split("#", 1)[0].strip()
        if not val:
            missing.append(f"{key}= (empty value)")
            continue
        # MemoryDenyWriteExecute: accept true; =false only with rationale.
        if key == "MemoryDenyWriteExecute":
            low = val.lower()
            if low == "true":
                continue
            if low == "false" and has_comment:
                continue
            missing.append(f"{key}={val} (need true OR false+rationale)")
            continue
        # RestrictAddressFamilies: accept any non-empty AF list; the
        # narrower the better. Empty/AF_UNSPEC is rejected.
        if key == "RestrictAddressFamilies":
            low = val.lower()
            if "af_unspec" in low or low in ("any", "true", "false"):
                missing.append(f"{key}={val} (must enumerate AF list)")
            continue

    assert not missing, (
        f"{unit.name} inference-service hardening (R346/SDD-036) "
        f"insufficient: {missing}. Inline-comment waiver acceptable for "
        f"codegen-needs-W^X tradeoffs."
    )
