"""Unit tests for the Phase-0 cockpit action-execution primitive.

Covers the security-critical, mechanism-independent core of
`scripts/operator/_action_exec.py`: the R10212 selfdef boundary (selfdef-owned
controls NEVER execute locally), placeholder validation (enum allowlists +
strict free-value regex, shell-injection rejection), the privileged-control
gates (operator-key presence + explicit confirm), and the dry-run default.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_PATH = REPO_ROOT / "scripts" / "operator" / "_action_exec.py"


def _load():
    spec = importlib.util.spec_from_file_location("_action_exec", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


AE = _load()


# ── registry + classification ────────────────────────────────────────────────

def test_registry_loads_11_controls():
    reg = AE.load_registry()
    assert len(reg) == 11, f"expected 11 controls, got {sorted(reg)}"


def test_selfdef_owned_matches_registry_state_path():
    """The SELFDEF_OWNED boundary set must exactly equal the controls whose
    registry `state_path` is owned by selfdef / tetragon — so a registry edit
    cannot silently widen local execution."""
    reg = AE.load_registry()
    derived = {cid for cid, c in reg.items()
               if "selfdef" in str(c.get("state_path", "")).lower()
               or "tetragon" in str(c.get("state_path", "")).lower()}
    assert derived == set(AE.SELFDEF_OWNED), (
        f"boundary drift: state_path-derived {sorted(derived)} vs "
        f"SELFDEF_OWNED {sorted(AE.SELFDEF_OWNED)}")


def test_classification_9_local_2_proxy():
    c = AE.owned_controls()
    assert len(c["local"]) == 9 and c["proxy"] == ["perimeter", "selfdef"]
    assert "selfdef" not in c["local"] and "perimeter" not in c["local"]


# ── the hard R10212 boundary ─────────────────────────────────────────────────

@pytest.mark.parametrize("cid,args", [
    ("selfdef", {"verb": "on"}),
    ("selfdef", {"verb": "off"}),
    ("perimeter", {}),
])
def test_selfdef_owned_never_executes(cid, args):
    r = AE.execute(cid, args, confirm=True, dry_run=False)
    assert r["ok"] is False and r["code"] == 409 and r.get("boundary") is True
    assert "proxy_cli" in r  # panel copies the signed verb instead


def test_selfdef_boundary_holds_even_live_and_confirmed():
    """Even with live execution requested + confirm + (faked) key, a
    selfdef-owned control must not run."""
    r = AE.execute("selfdef", {"verb": "on"}, confirm=True, dry_run=False)
    assert r.get("boundary") is True and "exit_code" not in r


# ── placeholder validation ───────────────────────────────────────────────────

def test_free_placeholder_accepts_option_value():
    argv, err = AE.resolve_argv(AE.load_registry()["cpu-mode"], {"mode": "balanced"})
    assert err is None and argv == ["sovereign-osctl", "cpu-mode", "set", "balanced"]


def test_enum_placeholder_validates_verb():
    reg = AE.load_registry()
    argv, err = AE.resolve_argv(reg["dashboard-toggle"], {"verb": "enable", "slug": "d-03-model-health"})
    assert err is None and argv[:3] == ["sovereign-osctl", "dashboards", "enable"]
    _, bad = AE.resolve_argv(reg["dashboard-toggle"], {"verb": "nuke", "slug": "x"})
    assert bad is not None


@pytest.mark.parametrize("bad", [
    "balanced; rm -rf /", "balanced && reboot", "$(whoami)", "a b", "../etc/passwd",
    "balanced|tee", "`id`",
])
def test_shell_injection_rejected(bad):
    r = AE.execute("cpu-mode", {"mode": bad}, dry_run=True)
    assert r["ok"] is False and r["code"] == 400


def test_missing_value_rejected():
    r = AE.execute("cpu-mode", {}, dry_run=True)
    assert r["ok"] is False and r["code"] == 400


# ── privileged gates ─────────────────────────────────────────────────────────

def test_unknown_control_404():
    r = AE.execute("no-such-control", {}, dry_run=True)
    assert r["ok"] is False and r["code"] == 404


def test_privileged_requires_operator_key(monkeypatch):
    monkeypatch.delenv("SOVEREIGN_OS_MOK_KEY", raising=False)
    monkeypatch.delenv("SOVEREIGN_OS_PK_KEY", raising=False)
    monkeypatch.setattr(AE, "operator_key_loaded", lambda: False)
    r = AE.execute("cpu-mode", {"mode": "balanced"}, confirm=True, dry_run=True)
    assert r["ok"] is False and r["code"] == 403 and "operator key" in r["error"]


def test_privileged_requires_confirm(monkeypatch):
    monkeypatch.setattr(AE, "operator_key_loaded", lambda: True)
    r = AE.execute("cpu-mode", {"mode": "balanced"}, confirm=False, dry_run=True)
    assert r["ok"] is False and r["code"] == 403 and r.get("confirm_required") is True


def test_privileged_dry_run_ok_with_key_and_confirm(monkeypatch):
    monkeypatch.setattr(AE, "operator_key_loaded", lambda: True)
    r = AE.execute("cpu-mode", {"mode": "balanced"}, confirm=True, dry_run=True)
    assert r["ok"] is True and r["dry_run"] is True
    assert r["argv"] == ["sovereign-osctl", "cpu-mode", "set", "balanced"]
    # would_run is either the bare argv (already root) or sudo -n wrapped.
    assert r["would_run"] == r["argv"] or r["would_run"][:2] == [AE.SUDO, "-n"]


def test_nonprivileged_dry_run_needs_no_key():
    # flex-profile is privileged:false — should dry-run without key/confirm.
    r = AE.execute("flex-profile", {"key": "kv_cache_dtype", "value": "fp8"}, dry_run=True)
    assert r["ok"] is True and r["dry_run"] is True


def test_default_dry_run_is_safe():
    """Importing the module must not enable live execution by default."""
    assert AE._DEFAULT_DRY_RUN is True


# ── observability ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("cid,args,confirm,outcome", [
    ("selfdef", {"verb": "on"}, True, "boundary-reject"),
    ("cpu-mode", {"mode": "balanced; rm -rf /"}, False, "validation-reject"),
    ("no-such", {}, False, "unknown-control"),
    ("flex-profile", {"key": "kv_cache_dtype", "value": "fp8"}, False, "dry-run"),
])
def test_metric_emitted_per_outcome(tmp_path, monkeypatch, cid, args, confirm, outcome):
    monkeypatch.setenv("SOVEREIGN_OS_METRICS_DIR", str(tmp_path))
    AE.execute(cid, args, confirm=confirm, dry_run=True)
    prom = (tmp_path / "sovereign-os-cockpit-action-exec.prom").read_text()
    assert AE._METRIC_NAME in prom
    assert f'outcome="{outcome}"' in prom
    assert f'control_id="{cid}"' in prom


def test_confirm_required_metric(tmp_path, monkeypatch):
    monkeypatch.setenv("SOVEREIGN_OS_METRICS_DIR", str(tmp_path))
    monkeypatch.setattr(AE, "operator_key_loaded", lambda: True)
    AE.execute("cpu-mode", {"mode": "balanced"}, confirm=False, dry_run=True)
    prom = (tmp_path / "sovereign-os-cockpit-action-exec.prom").read_text()
    assert 'outcome="confirm-required"' in prom
