"""Lint: the cockpit sudoer allowlist stays in sync with the control registry
and never breaches the R10212 selfdef boundary.

Guards the Phase-0 execution primitive (`scripts/operator/_action_exec.py`) +
its NOPASSWD allowlist (`config/sudoers.d/sovereign-os-cockpit`, DRAFT). Every
sovereign-os-OWNED control's verb prefix must be allow-listed; selfdef-owned
verbs (selfdef, perimeter) must NEVER appear; the file must stay marked DRAFT so
it is not silently treated as active before operator review.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SUDOERS = REPO_ROOT / "config" / "sudoers.d" / "sovereign-os-cockpit"
REGISTRY = REPO_ROOT / "config" / "control-systems.yaml"
MOD = REPO_ROOT / "scripts" / "operator" / "_action_exec.py"


def _ae():
    spec = importlib.util.spec_from_file_location("_action_exec", MOD)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _registry() -> dict[str, dict]:
    doc = yaml.safe_load(REGISTRY.read_text())
    return {s["id"]: s for s in doc.get("systems", [])}


def _verb_prefix(change_cli: str) -> str:
    """The fixed literal prefix of a change_cli, up to the first placeholder."""
    toks = []
    for t in change_cli.split():
        if t.startswith("<") or t.startswith("{"):
            break
        toks.append(t)
    return " ".join(toks)


def test_sudoers_present_and_draft():
    assert SUDOERS.is_file(), f"missing {SUDOERS}"
    body = SUDOERS.read_text()
    assert "DRAFT" in body and "SUPERSEDED" in body, (
        "the sudoers allowlist must stay marked DRAFT (preview of the "
        "operator-sudoers.sh controls-bucket extension) until it is folded in")


def test_every_sovereign_os_owned_verb_is_allowlisted():
    ae = _ae()
    reg = _registry()
    body = SUDOERS.read_text()
    for cid, ctl in reg.items():
        if cid in ae.SELFDEF_OWNED:
            continue
        prefix = _verb_prefix(ctl.get("change_cli", ""))
        assert prefix, f"{cid}: no verb prefix parsed from change_cli"
        assert prefix in body, (
            f"sovereign-os-owned control {cid!r} verb {prefix!r} is NOT in the "
            f"sudoers allowlist — a wired control must have a reviewed entry")


def test_selfdef_owned_verbs_never_allowlisted():
    ae = _ae()
    reg = _registry()
    body = SUDOERS.read_text()
    for cid in ae.SELFDEF_OWNED:
        # the selfdef/perimeter change verb must not be grantable
        verb = _verb_prefix(reg[cid].get("change_cli", ""))
        # allow the word to appear in a comment, but not as an allowlisted
        # /usr/local/bin/sovereign-osctl <verb> command line
        assert f"sovereign-osctl {verb.split(' ',1)[1] if ' ' in verb else verb}" not in \
            "\n".join(l for l in body.splitlines() if not l.lstrip().startswith("#")), (
            f"selfdef-owned control {cid!r} must never be in the sudoers allowlist "
            f"(R10212 boundary)")


def test_boundary_set_matches_registry():
    """Re-assert (independently of the unit test) that SELFDEF_OWNED equals the
    selfdef/tetragon-owned controls."""
    ae = _ae()
    reg = _registry()
    derived = {cid for cid, c in reg.items()
               if "selfdef" in str(c.get("state_path", "")).lower()
               or "tetragon" in str(c.get("state_path", "")).lower()}
    assert derived == set(ae.SELFDEF_OWNED)
