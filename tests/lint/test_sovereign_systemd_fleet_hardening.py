"""sovereign-os systemd service fleet hardening contract.

sovereign-os ships 63 systemd services at systemd/system/*.service.
About 26 have per-API contract tests covering the 3 invariants
(unit_present + loopback_default + defense_in_depth). The remaining
~37 services have no contract test pinning their hardening posture.

A silent regression of any hardening clause on any service widens
that service's host capability surface. With 63 services the per-
unit probability is low but the aggregate blast radius is large.
This fleet-level gate pins the universal hardening minimums every
service must carry, leaving per-service semantic invariants
(specific ExecStart / API binding / etc) to the existing per-API
gates.

Fleet hardening minimums verified empirically present today (every
non-outlier service carries these — distribution checked 2026-06-06):

  - NoNewPrivileges=true        (63/63 — no exception)
  - ProtectControlGroups=true   (63/63 — no exception)
  - RestrictRealtime=true       (63/63 — no exception)
  - ProtectKernelTunables=true  (62/63 — 1 documented exemption)
  - ProtectSystem=strict|full   (63/63 — `full` is the looser variant
                                  for services that legitimately need
                                  to write to /etc or /usr)

EXEMPT list: services that legitimately cannot carry a clause are
registered here with a reason. Currently:
  - sovereign-hugepages-sizer: writes to /sys/kernel/mm/transparent_
    hugepage which is a /sys-tunables path that ProtectKernelTunables
    blocks. The hugepages sizer's whole purpose is to mutate the
    kernel hugepage setting — exemption is intentional.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SYSTEMD_DIR = REPO_ROOT / "systemd" / "system"


# (unit_filename, clause_name) tuples that legitimately omit the
# clause. Each pair needs a reason in the docstring above.
EXEMPT = {
    ("sovereign-hugepages-sizer.service", "ProtectKernelTunables=true"),
}


REQUIRED_CLAUSES = (
    "NoNewPrivileges=true",
    "ProtectControlGroups=true",
    "RestrictRealtime=true",
    "ProtectKernelTunables=true",
)


def _services() -> list[Path]:
    if not SYSTEMD_DIR.is_dir():
        return []
    return sorted(SYSTEMD_DIR.glob("*.service"))


def test_systemd_dir_present():
    assert SYSTEMD_DIR.is_dir(), f"systemd/system/ not found at {SYSTEMD_DIR}"


def test_at_least_one_service():
    services = _services()
    assert services, f"no .service files found under {SYSTEMD_DIR}"


def test_every_service_carries_universal_hardening_clauses():
    """Every service must carry each of the 4 universal hardening
    clauses (NoNewPrivileges, ProtectControlGroups, RestrictRealtime,
    ProtectKernelTunables) unless the (service, clause) pair is in
    the documented EXEMPT set."""
    violations: list[str] = []
    for svc in _services():
        text = svc.read_text(encoding="utf-8", errors="replace")
        name = svc.name
        for clause in REQUIRED_CLAUSES:
            if (name, clause) in EXEMPT:
                continue
            # Check for literal line presence (with optional whitespace)
            found = False
            for line in text.splitlines():
                if line.strip() == clause:
                    found = True
                    break
            if not found:
                violations.append(f"{name}: missing {clause}")
    assert not violations, (
        f"systemd services missing required universal hardening clauses "
        f"(register exemption with reason if intentional): {violations}"
    )


def test_every_service_carries_protect_system():
    """ProtectSystem must be set to either `strict` (read-only root)
    or `full` (read-only /usr/bin/etc/boot, more permissive). A
    service without ProtectSystem at all has unrestricted root
    write — silent regression here would weaken every service's
    confinement envelope at the same time."""
    missing: list[str] = []
    for svc in _services():
        text = svc.read_text(encoding="utf-8", errors="replace")
        has_strict = "\nProtectSystem=strict" in text or text.startswith("ProtectSystem=strict")
        has_full = "\nProtectSystem=full" in text or text.startswith("ProtectSystem=full")
        if not (has_strict or has_full):
            missing.append(svc.name)
    assert not missing, (
        f"systemd services missing ProtectSystem={{strict|full}}: {missing}"
    )


def test_exempt_entries_reference_real_services():
    """The EXEMPT list must reference real on-disk services + real
    hardening clauses. A dead exemption indicates a service was
    deleted without cleaning up its exemption."""
    services_present = {svc.name for svc in _services()}
    dead: list[tuple[str, str]] = []
    for name, clause in EXEMPT:
        if name not in services_present:
            dead.append((name, "service not on disk"))
        if clause not in REQUIRED_CLAUSES:
            dead.append((name, f"clause {clause!r} not in REQUIRED_CLAUSES"))
    assert not dead, f"dead EXEMPT entries: {dead}"
