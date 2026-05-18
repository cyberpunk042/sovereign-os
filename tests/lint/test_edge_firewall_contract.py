"""R451 (E11.M9) — edge-firewall alternative contract lint.

Per operator §1g verbatim:
  "even if there isn't an Edge firewall its possible to install the
   equivalent or even more advanced if we want on this machine if we
   would be ready to pay the performance price..."

6th substantive feature of §1g/§1h Epic E11 arc:
  R446 — E11.M4 Nemotron 3 (partial)
  R447 — E11.M6 bashrc opt-in
  R448 — E11.M5 global-history
  R449 — E11.M8 network-edge
  R450 — E11.M7 auth-tier ladder
  R451 — E11.M9 edge-firewall alternative
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EF_PY = REPO_ROOT / "scripts" / "operator" / "edge-firewall.py"
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"

# §1g operator-named install-class candidates (LOW → HIGH overhead)
EXPECTED_CANDIDATES = [
    "nftables-baseline",
    "fail2ban",
    "crowdsec",
    "suricata",
]


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# --- Structural ---


def test_edge_firewall_script_exists():
    assert EF_PY.is_file(), f"missing {EF_PY}"


def test_edge_firewall_executable():
    assert os.access(EF_PY, os.X_OK), f"{EF_PY} not executable"


def test_python3_shebang():
    body = _read(EF_PY)
    assert body.startswith("#!/usr/bin/env python3")


def test_documents_e11_m9_origin():
    body = _read(EF_PY)
    assert "E11.M9" in body and "§1g" in body


def test_quotes_operator_verbatim_1g_phrase():
    """§1g verbatim performance-price phrase MUST appear."""
    body = _read(EF_PY)
    flat = re.sub(r"\s+", " ", body)
    for phrase in (
        "even if there isn't an Edge firewall",
        "ready to pay the performance price",
        "Sharevdi Fanless Firewall Mini PC",
        "Intel J3710/N3710",
        "i226-V",
        "AES NI",
    ):
        assert phrase in flat, (
            f"missing operator §1g verbatim phrase {phrase!r}"
        )


# --- 4-candidate ladder ---


def test_candidates_catalog_defined():
    body = _read(EF_PY)
    assert "CANDIDATES" in body, "missing CANDIDATES catalog constant"
    for c in EXPECTED_CANDIDATES:
        assert f'"{c}"' in body, f"CANDIDATES missing {c!r}"


def test_each_candidate_has_level_field():
    body = _read(EF_PY)
    for n in range(1, 5):
        assert f'"level": {n}' in body, (
            f"CANDIDATES missing level={n}"
        )


def test_each_candidate_has_perf_cost_field():
    body = _read(EF_PY)
    n = body.count('"perf_cost":')
    assert n >= 4, f"only {n} perf_cost fields (expected ≥4)"


def test_each_candidate_has_threat_model_field():
    body = _read(EF_PY)
    n = body.count('"threat_model":')
    assert n >= 4, f"only {n} threat_model fields (expected ≥4)"


def test_each_candidate_has_operator_named_use_field():
    body = _read(EF_PY)
    n = body.count('"operator_named_use":')
    assert n >= 4, f"only {n} operator_named_use fields (expected ≥4)"


def test_each_candidate_has_apt_packages_field():
    body = _read(EF_PY)
    n = body.count('"apt_packages":')
    assert n >= 4, f"only {n} apt_packages fields (expected ≥4)"


def test_each_candidate_has_systemd_units_field():
    body = _read(EF_PY)
    n = body.count('"systemd_units":')
    assert n >= 4, f"only {n} systemd_units fields (expected ≥4)"


def test_each_candidate_has_config_paths_field():
    body = _read(EF_PY)
    n = body.count('"config_paths":')
    assert n >= 4, f"only {n} config_paths fields (expected ≥4)"


# --- CLI surface ---


def test_supports_state_verb():
    body = _read(EF_PY)
    assert '"state"' in body


def test_supports_candidates_verb():
    body = _read(EF_PY)
    assert '"candidates"' in body


def test_supports_recommend_verb():
    body = _read(EF_PY)
    assert '"recommend"' in body


def test_supports_install_plan_verb():
    body = _read(EF_PY)
    assert '"install-plan"' in body


def test_supports_install_verb():
    body = _read(EF_PY)
    assert '"install"' in body


def test_supports_wizard_verb():
    """R482 (E11.M9+) — install-wizard TUI surface, closes surface-map
    FUTURE waiver 'install-wizard TUI worthwhile'."""
    body = _read(EF_PY)
    assert '"wizard"' in body, "edge-firewall.py missing wizard verb"
    assert "def cmd_wizard(" in body, (
        "edge-firewall.py missing cmd_wizard() function"
    )


def test_wizard_has_ansi_clear_screen():
    """The wizard MUST clear-screen between pages — that's what makes
    it a TUI surface vs a one-shot CLI."""
    body = _read(EF_PY)
    assert "\\x1b[2J" in body, (
        "edge-firewall.py wizard missing ANSI clear-screen (TUI hint)"
    )


def test_wizard_supports_accept_default():
    """Operator-discoverable: --accept-default makes the wizard
    scriptable + L3-testable (no interactive stdin)."""
    body = _read(EF_PY)
    assert "--accept-default" in body, (
        "wizard missing --accept-default for scripted/L3 use"
    )


def test_wizard_routes_through_triple_gate():
    """The wizard MUST NOT bypass cmd_install's triple-gate; final
    install step calls cmd_install() (not direct apt/systemctl)."""
    body = _read(EF_PY)
    assert "cmd_install(" in body, (
        "wizard missing handoff to cmd_install() — triple-gate bypass risk"
    )


def test_wizard_emits_metric_with_wizard_label():
    """Layer B observability: wizard emits Layer B metric with
    verb=wizard so it aggregates separately from other verbs."""
    body = _read(EF_PY)
    assert '"wizard"' in body and (
        "sovereign_os_operator_edge_firewall_query_total" in body
    ), "wizard missing query_total metric emission"


def test_install_has_triple_gate():
    """`install` MUST require --apply + --confirm-install."""
    body = _read(EF_PY)
    assert "--apply" in body, "install missing --apply gate"
    assert "--confirm-install" in body, (
        "install missing --confirm-install gate"
    )


def test_json_and_human_format_flags():
    body = _read(EF_PY)
    assert "--json" in body and "--human" in body


# --- R449 bridge (upstream-state-aware recommendations) ---


def test_shells_out_to_network_topology():
    """recommendation MUST reach into R449 network-topology for
    upstream state — operator §1g paired surface."""
    body = _read(EF_PY)
    assert "network-topology.py" in body, (
        "missing R449 network-topology.py bridge"
    )


# --- DRY-RUN + env overlay ---


def test_supports_dry_run():
    body = _read(EF_PY)
    assert "SOVEREIGN_OS_DRY_RUN" in body


def test_supports_dedicated_dry_run_env():
    body = _read(EF_PY)
    assert "SOVEREIGN_OS_EDGE_FIREWALL_DRY_RUN" in body


# --- Metric ---


def test_emits_layer_b_metric():
    body = _read(EF_PY)
    assert "sovereign_os_operator_edge_firewall_query_total" in body


# --- osctl integration ---


def test_osctl_dispatches_edge_firewall():
    body = _read(OSCTL)
    assert "edge-firewall)" in body, (
        "osctl missing edge-firewall) dispatcher"
    )
    assert "edge-firewall.py" in body, (
        "osctl dispatcher doesn't reference edge-firewall.py"
    )


def test_osctl_help_documents_edge_firewall_verbs():
    body = _read(OSCTL)
    for sub in (
        "edge-firewall state",
        "edge-firewall candidates",
        "edge-firewall recommend",
        "edge-firewall install-plan",
        "edge-firewall install",
        "edge-firewall wizard",
    ):
        assert sub in body, f"osctl help missing {sub!r}"


def test_osctl_help_references_e11_m9():
    body = _read(OSCTL)
    assert "E11.M9" in body


# --- Smoke tests ---


def test_candidates_verb_runs():
    """candidates --json must return all 4 candidates in correct
    operator-named order."""
    result = subprocess.run(
        ["python3", str(EF_PY), "candidates", "--json"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, (
        f"candidates --json failed: stderr={result.stderr[:200]}"
    )
    data = json.loads(result.stdout)
    assert "candidates" in data
    cands = data["candidates"]
    assert len(cands) == 4, f"expected 4 candidates, got {len(cands)}"
    actual = [c["id"] for c in cands]
    assert actual == EXPECTED_CANDIDATES, (
        f"candidate order drifted: {actual} vs {EXPECTED_CANDIDATES}"
    )


def test_recommend_verb_runs():
    result = subprocess.run(
        ["python3", str(EF_PY), "recommend", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, (
        f"recommend --json failed: stderr={result.stderr[:200]}"
    )
    data = json.loads(result.stdout)
    assert "recommendations" in data
    assert "upstream_tier" in data


def test_install_plan_verb_runs():
    result = subprocess.run(
        ["python3", str(EF_PY), "install-plan", "fail2ban", "--json"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, (
        f"install-plan failed: stderr={result.stderr[:200]}"
    )
    data = json.loads(result.stdout)
    assert data["candidate"] == "fail2ban"
    assert "install_steps" in data
    assert "rollback_steps" in data


def test_install_preview_mode_runs_without_writing():
    """install without --apply MUST preview, NOT execute."""
    result = subprocess.run(
        ["python3", str(EF_PY), "install", "fail2ban", "--json"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, (
        f"install preview failed: stderr={result.stderr[:200]}"
    )
    combined = (result.stdout + result.stderr).lower()
    assert "preview" in combined or "--apply" in combined, (
        "install without --apply should indicate preview / gate-missing"
    )


def test_install_unknown_candidate_fails():
    """install with an unknown candidate MUST exit non-zero."""
    result = subprocess.run(
        ["python3", str(EF_PY), "install", "bogus-candidate"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode != 0, (
        "install with unknown candidate should fail"
    )


def test_wizard_runs_non_interactive():
    """The wizard MUST run end-to-end under --accept-default with
    SOVEREIGN_OS_DRY_RUN=1 (zero stdin reads, exits at preview)."""
    env = os.environ.copy()
    env["SOVEREIGN_OS_DRY_RUN"] = "1"
    result = subprocess.run(
        ["python3", str(EF_PY), "wizard", "--accept-default"],
        capture_output=True, text=True, timeout=15, env=env,
        stdin=subprocess.DEVNULL,
    )
    assert result.returncode == 0, (
        f"wizard --accept-default failed: rc={result.returncode}\n"
        f"  stderr={result.stderr[:300]}"
    )
    combined = result.stdout + result.stderr
    assert "PAGE 1/4" in combined, "wizard missing page-1 marker"
    assert "PAGE 3/4" in combined, "wizard missing page-3 marker"
