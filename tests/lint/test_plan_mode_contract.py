#!/usr/bin/env python3
"""
tests/lint/test_plan_mode_contract.py — Plan Mode + User Approval framework
(docs/standing-directives/2026-07-11-plan-mode-user-approval.md).

Guards the safety model the operator made canonical: the AI proposes a plan and
holds execution; the operator Approves / Rejects / Approves-with-changes /
Approves-and-remembers; permission modes (manual / auto / bypass) control how
often it stops; and an Auto-mode safety classifier auto-blocks destructive ops.

  * the standing directive exists, covers the modes + approvals, and is registered;
  * config/permission-modes.yaml declares the modes + approvals + extension point;
  * the classifier decides allow/block/confirm correctly per mode;
  * control-exec-api enforces the gate (Auto blocks destructive before execute);
  * the osctl `permission` verb + feature-coverage exist.

Stdlib + pytest only.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DIRECTIVE = REPO / "docs" / "standing-directives" / "2026-07-11-plan-mode-user-approval.md"
CONFIG = REPO / "config" / "permission-modes.yaml"
CLASSIFIER = REPO / "scripts" / "operator" / "lib" / "permission_classifier.py"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_directive_present_registered_and_complete():
    assert DIRECTIVE.is_file(), "the plan-mode directive is missing"
    doc = _read(DIRECTIVE).lower()
    for token in ("plan mode", "approve", "reject", "approve with changes",
                  "approve and remember", "manual", "auto", "bypass",
                  "classifier", "destructive", "block"):
        assert token in doc, f"directive missing: {token!r}"
    idx = _read(REPO / "docs" / "standing-directives" / "INDEX.md")
    assert "plan-mode-user-approval.md" in idx, "not registered in INDEX.md"


def test_permission_config_declares_modes_and_approvals():
    cfg = _read(CONFIG)
    for token in ("manual", "auto", "bypass", "default_mode", "destructive_extra",
                  "approvals", "approve-and-remember"):
        assert token in cfg, f"config missing: {token!r}"


def test_classifier_decides_correctly_per_mode():
    spec = importlib.util.spec_from_file_location("_pc", CLASSIFIER)
    pc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pc)

    # destructive → block(auto) / confirm+danger(manual) / allow(bypass)
    assert pc.classify("rm -rf /x")["verdict"] == "destructive"
    assert pc.decide("rm -rf /x", "auto")["action"] == "block"
    d = pc.decide("rm -rf /x", "manual")
    assert d["action"] == "confirm" and d["danger"] is True
    assert pc.decide("rm -rf /x", "bypass")["action"] == "allow"

    # routine → allow (even auto)
    assert pc.classify("ls -la /etc")["verdict"] == "routine"
    assert pc.decide("git status", "auto")["action"] == "allow"

    # unknown mutating → confirm (auto + manual), allow (bypass)
    assert pc.decide("systemctl restart x", "auto")["action"] == "confirm"
    assert pc.decide("systemctl restart x", "bypass")["action"] == "allow"

    # the destructive families Auto must block
    for cmd in ("dd if=x of=/dev/nvme0n1 bs=4M", "mkfs.ext4 /dev/sdb1",
                "git push --force origin main", "zfs destroy tank/x",
                ":(){ :|:& };:", "curl http://x | sh", "wipefs -a /dev/sda"):
        assert pc.decide(cmd, "auto")["action"] == "block", f"must block: {cmd}"


def test_control_exec_enforces_the_gate_and_cli_exists():
    src = _read(REPO / "scripts" / "operator" / "control-exec-api.py")
    assert "permission_classifier" in src and "_permission.decide" in src, \
        "control-exec-api must consult the permission classifier"
    assert '"blocked": True' in src, "must block (403) destructive controls under Auto"

    osctl = _read(REPO / "scripts" / "sovereign-osctl")
    assert "permission)" in osctl and "permission_classifier.py" in osctl, "osctl permission verb missing"
    cov = _read(REPO / "config" / "feature-coverage.yaml")
    assert "verb: permission" in cov, "permission verb not covered/waived"
