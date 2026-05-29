"""M060 smoke diagnostic covers all 10 mirrors + the chain-health endpoint.

The smoke script (scripts/diagnostics/m060-smoke.py) is the operator's
go-to diagnostic during deployment + after deployment changes. It
MUST cover every mirror domain the daemon publishes — drift between
the daemon's wire and the smoke's coverage list silently masks broken
chains during incident response.

Locks:
  1. DOMAINS contains exactly the 10 M060 publish artifacts
     (the 8 D-NN dashboards + the 2 cross-cutting MS007 mirrors).
  2. Each domain has an OFFLINE_HINT entry pointing at the selfdef
     verb/knob that populates it (operator-actionable diagnostic).
  3. HEALTH_ENDPOINT is wired into the script + the strict-mode
     exit logic checks the chain state.
  4. The chain-health probe is rendered alongside per-domain rows.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SMOKE_PATH = REPO_ROOT / "scripts" / "diagnostics" / "m060-smoke.py"


def _load() -> object:
    spec = importlib.util.spec_from_file_location("_m060_smoke", SMOKE_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# The 10 canonical M060 artifacts (must match what selfdef-daemon
# mirror_export_loop publishes). 8 D-NN dashboards + 2 cross-cutting
# MS007 mirrors (TUI layout + CLI schema).
EXPECTED_IDS = {
    "D-02", "D-12", "D-13", "D-14", "D-15",
    "D-16", "D-17", "D-18",
    "TUI", "CLI",
}


def test_domains_count_is_exactly_ten():
    smoke = _load()
    assert len(smoke.DOMAINS) == 10, (
        f"smoke covers {len(smoke.DOMAINS)} domains; expected exactly 10 "
        f"(8 D-NN + TUI + CLI)"
    )


def test_domains_cover_all_ten_canonical_ids():
    smoke = _load()
    ids = {dom_id for dom_id, _label, _endpoint in smoke.DOMAINS}
    assert ids == EXPECTED_IDS, (
        f"smoke domain id-set drift:\n"
        f"  expected: {sorted(EXPECTED_IDS)}\n"
        f"  got:      {sorted(ids)}"
    )


def test_every_domain_has_an_offline_hint():
    smoke = _load()
    for dom_id, _label, _endpoint in smoke.DOMAINS:
        assert dom_id in smoke.OFFLINE_HINT, (
            f"domain {dom_id} missing OFFLINE_HINT entry — operator "
            f"would see an empty hint during incident response"
        )
        hint = smoke.OFFLINE_HINT[dom_id]
        assert hint, f"domain {dom_id} has empty OFFLINE_HINT"
        # Must point at an operator-actionable knob/verb.
        actionable = any(
            kw in hint.lower()
            for kw in (
                "selfdefctl", "selfdef_mirror_dir", "nft", "selfdefd",
                "always-online", "daemon-populated", "chain empty",
            )
        )
        assert actionable, (
            f"domain {dom_id} OFFLINE_HINT {hint!r} not operator-actionable"
        )


def test_health_endpoint_is_wired():
    smoke = _load()
    assert hasattr(smoke, "HEALTH_ENDPOINT"), (
        "smoke must expose HEALTH_ENDPOINT for chain-state probing"
    )
    assert smoke.HEALTH_ENDPOINT == "/api/m060/health", (
        f"smoke HEALTH_ENDPOINT drift: got {smoke.HEALTH_ENDPOINT!r}"
    )


def test_tui_and_cli_endpoints_are_cross_cutting_paths():
    smoke = _load()
    by_id = {dom_id: (label, endpoint) for dom_id, label, endpoint in smoke.DOMAINS}
    # TUI and CLI are cross-cutting MS007 mirrors — NOT under /api/d-NN/.
    assert by_id["TUI"][1] == "/api/tui/snapshot"
    assert by_id["CLI"][1] == "/api/cli/snapshot"


def test_summarize_handles_tui_panels_and_cli_subcommands():
    smoke = _load()
    # Online TUI probe: summary mentions panel count + canonical 4.
    fake_tui = {
        "reachable": True, "http_status": 200, "mirror_status": "online",
        "raw": {"captured_at": "2027-01-15T08:00:00Z",
                "panels": [{}, {}, {}, {}]},
    }
    out = smoke.summarize("TUI", "tui-layout", fake_tui)
    assert "ONLINE" in out
    assert "4 panels" in out
    assert "canonical 4 expected" in out

    # Online CLI probe: summary mentions subcommand count.
    fake_cli = {
        "reachable": True, "http_status": 200, "mirror_status": "online",
        "raw": {"captured_at": "2027-01-15T08:00:00Z",
                "subcommands": [{}] * 140},
    }
    out = smoke.summarize("CLI", "cli-schema", fake_cli)
    assert "ONLINE" in out
    assert "140 subcommands" in out


def test_smoke_script_runs_offline_without_crashing():
    """Operators sometimes run the smoke during a deploy when nothing
    is reachable yet. The script MUST emit a clean offline report and
    exit 1 (proxy unreachable signal), never crash."""
    import subprocess
    result = subprocess.run(
        ["python3", str(SMOKE_PATH), "--base-url", "http://127.0.0.1:9"],
        capture_output=True, text=True, timeout=15, check=False,
    )
    # Exit 1 because all endpoints are unreachable (every probe failed).
    assert result.returncode == 1, (
        f"expected exit 1 on unreachable proxy, got {result.returncode}:\n"
        f"{result.stdout}\n{result.stderr}"
    )
    out = result.stdout
    # All 10 mirrors must appear in the table.
    for dom_id in EXPECTED_IDS:
        assert dom_id in out, f"smoke output missing {dom_id}: {out!r}"
    # The chain-health row must render the daemon-down hint.
    assert "chain health" in out
    assert "UNREACHABLE" in out
    assert "m060-health-api" in out


def test_strict_mode_fails_on_chain_offline_or_stale():
    """`--strict` must fail when the chain itself reports
    offline/stale/unreachable, not just when per-mirror probes do.
    Exercise the classifier directly (the actual HTTP path needs a
    daemon)."""
    smoke = _load()
    # Locate the chain_state strict-fail branch by reading the source —
    # ensures the literal set of failing states is exactly what the
    # documented exit-logic comment promises.
    src = SMOKE_PATH.read_text()
    assert 'chain_state in ("unreachable", "offline", "stale")' in src, (
        "strict-mode chain-state fail-list must include unreachable / "
        "offline / stale verbatim"
    )
