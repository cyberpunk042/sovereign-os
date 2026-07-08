"""M081 Whitelabel-Architecture contract lint.

Locks `config/server/m081-whitelabel-architecture.yaml` to the M081 spec: the
Debian surface audit (E0778), the categorization taxonomy (E0779), legal
obligations (E0780), the whitelabel profile schema (E0781), per-surface rendering
strategies (E0782), lifecycle staging (E0783), evolvability (E0784), the
legal-compliance validator (E0785), the default placeholder (E0786), and Stage
Gate 4 (E0787). No minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "server" / "m081-whitelabel-architecture.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M081-whitelabel-architecture-audit-and-mechanism.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M081"


def test_nine_audit_surfaces():
    s = [x["surface"] for x in _c()["audit_surfaces"]]
    assert s == ["filesystem", "package-mgr", "boot", "installer", "desktop", "kernel",
                 "docs", "network", "telemetry"], f"surface drift: {s}"


def test_categorization_four_taxonomy():
    c = _c()["categorization"]["categories"]
    assert c == ["must-rebrand", "should-rebrand", "may-leave", "must-not-touch"]


def test_legal_obligations_three():
    lo = _c()["legal_obligations"]["requirements"]
    assert lo == ["Debian trademark", "DFSG", "GPL attribution"]


def test_whitelabel_schema_declarative():
    ws = _c()["whitelabel_schema"]
    assert ws["schema_file"] == "schemas/whitelabel.schema.yaml"
    assert "declarative whitelabel-profile YAML" in ws["shape"]


def test_four_rendering_strategies():
    rs = _c()["rendering_strategies"]["strategies"]
    assert rs == ["template-substitution", "file-overlay", "package-replacement",
                  "build-time-flag"]


def test_lifecycle_staging_three():
    ls = _c()["lifecycle_staging"]
    assert ls == ["pre-build patches", "install-time substitutions", "first-boot scripts"]


def test_legal_validator_must_not_touch():
    assert "must-not-touch" in _c()["legal_validator"]["rule"]
    assert "validation time" in _c()["legal_validator"]["rule"]


def test_stage_gate_4_and_default_placeholder():
    assert "no brand committed" in _c()["default_placeholder"]
    assert "reviews audit + mechanism together" in _c()["stage_gate_4"]


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M01343", "M01345", "M01352", "M01353", "M01354", "M01357", "M01361"):
        assert mod in body, f"{mod} not in the M081 milestone (must trace to spec)"
