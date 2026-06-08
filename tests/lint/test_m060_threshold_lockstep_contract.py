"""M060 cross-surface threshold-lockstep lint (sovereign-os side).

The M060 observability chain shares 3 invariants across surfaces:

  1. STALE_AGE_SECS = 300 (5 minutes)
     Appears as the `> 300` Prometheus alert expression for both
     observer-silent alerts, the daemon-side Rust const in
     selfdef-api::m060_health, the JS const in the master-
     dashboard banner classifier, and (implicitly) the doctor
     scripts that flag stale artifacts.

  2. 4 chain-state enum strings: online / degraded / stale /
     offline / unreachable (5 states actually — the m060-health-
     api emits all 5). Renaming one without the others breaks
     the multi-surface classifier.

  3. CHAIN_LINK label set: cli-mirror + mirror-domain.
     Each sub-chain alert carries chain_link=<label>; renaming
     one breaks Grafana filters AND the runbook deep-links.

Drift is the silent operator-misdirection hazard. Per-surface
contract tests catch drift WITHIN their surface; this test
catches drift BETWEEN them.

Optional partner-repo cross-reference via $SELFDEF_REPO_ROOT
verifies the selfdef-side Rust const lives at the canonical
value — closes the cross-repo loop matching the bidirectional
MS022 pattern shipped at sovereign-os commit `ac6b0ab` +
selfdef commit `625f3d9`.

Extension (this commit): the 8-domain M060 wire contract is now
locked across both repos. The selfdef-cli m060_doctor DOMAINS
array + selfdef-api m060_health ARTIFACT_NAMES list +
sovereign-os m060-smoke DOMAINS tuple + sovereign-os
mirror-domains dashboard panel description MUST reference the
SAME 8 D-NN IDs. Sister to selfdef commit a233057 which adds the
same 4 assertions on the selfdef side; bidirectional contract.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]

# Canonical M060 invariants.
STALE_AGE_SECS = 300  # 5 minutes
CHAIN_STATES = {"online", "degraded", "stale", "offline", "unreachable"}
CHAIN_LINK_LABELS = {"cli-mirror", "mirror-domain"}

# The canonical 8-domain M060 wire contract. Order matters because
# both the producer (selfdef m060_doctor DOMAINS) and the consumer
# (sovereign-os m060-smoke DOMAINS) iterate in this exact order;
# operators see textfile gauges + smoke-test output rows in this
# order. Reordering would silently break Grafana legend ordering
# + the per-domain timeseries panel.
CANONICAL_DOMAIN_IDS = (
    "D-02",  # active-profile
    "D-12",  # rules
    "D-13",  # grants
    "D-14",  # capability-tokens
    "D-15",  # sandboxes
    "D-16",  # audit-chain
    "D-17",  # quarantine
    "D-18",  # trust-scores
)

# The 8 D-NN-tied published-filenames in the selfdef-api/m060_health
# ARTIFACT_NAMES list. Plus the 2 MS007 cross-cutting artifacts
# (tui + cli) for a total of 10. The api endpoint reports all 10.
CANONICAL_D_NN_FILES = (
    "active-profile.json",
    "rules.json",
    "grants.json",
    "capability-tokens.json",
    "sandboxes.json",
    "audit.json",
    "quarantine.json",
    "trust-scores.json",
)
MS007_CROSS_CUTTING_FILES = ("tui.json", "cli.json")
CANONICAL_API_ARTIFACTS = set(CANONICAL_D_NN_FILES) | set(MS007_CROSS_CUTTING_FILES)

ALERTS_PATH = (
    REPO_ROOT / "config" / "prometheus" / "alerts" / "m060-chain-health.rules.yml"
)
MASTER_DASHBOARD = REPO_ROOT / "webapp" / "master-dashboard" / "index.html"
HEALTH_API = REPO_ROOT / "scripts" / "operator" / "m060-health-api.py"
SMOKE_SCRIPT = REPO_ROOT / "scripts" / "diagnostics" / "m060-smoke.py"
MIRROR_DOMAINS_DASHBOARD = (
    REPO_ROOT / "docs" / "observability" / "dashboards"
    / "sovereign-os-m060-mirror-domains.json"
)


def _read(path: Path) -> str:
    return path.read_text()


def _alert_rules() -> list[dict]:
    doc = yaml.safe_load(_read(ALERTS_PATH))
    return [r for g in doc["groups"] for r in g["rules"]]


def test_observer_silent_alerts_share_300_threshold():
    """Both observer-silent alerts (CliMirror + MirrorDomain) MUST
    use `> 300` — drift would silently misalign the page-trigger
    against the doctor's `last_run_unix` accounting."""
    by_name = {r["alert"]: r for r in _alert_rules()}
    for name in ("M060CliMirrorObserverSilent", "M060MirrorDomainObserverSilent"):
        expr = by_name[name]["expr"]
        assert "> 300" in expr, (
            f"alert {name!r} drift: expected '> 300' threshold; got: "
            f"{expr!r}"
        )


def test_master_dashboard_stale_age_matches_canonical_300s():
    """The master-dashboard tile-state classifier reads
    `M060_TILE_STALE_AGE_SECS = 5 * 60` (= 300). Drift = the tile
    turns yellow at a different age than the alert fires."""
    body = _read(MASTER_DASHBOARD)
    m = re.search(
        r"const M060_TILE_STALE_AGE_SECS\s*=\s*([0-9*\s]+);", body,
    )
    assert m is not None, (
        "master-dashboard missing M060_TILE_STALE_AGE_SECS const"
    )
    # Evaluate the literal (handles `5 * 60` or just `300`).
    value_expr = m.group(1).strip()
    value = eval(value_expr, {"__builtins__": {}}, {})
    assert value == STALE_AGE_SECS, (
        f"master-dashboard STALE_AGE_SECS drift: expected {STALE_AGE_SECS}, "
        f"got {value} (from literal {value_expr!r})"
    )


def test_health_api_advertises_canonical_state_set():
    """The m060-health-api's /version states list MUST match the
    canonical 5-state set. Drift = consumer code expecting one of
    the documented states gets a state it can't handle."""
    body = _read(HEALTH_API)
    # The version_payload literal carries the states list.
    states_match = re.search(
        r'"states":\s*\[([^\]]+)\]', body,
    )
    assert states_match is not None
    states_block = states_match.group(1)
    # Extract every quoted string in the block.
    found_states = set(re.findall(r'"([^"]+)"', states_block))
    assert found_states == CHAIN_STATES, (
        f"m060-health-api states drift: expected {CHAIN_STATES!r}, "
        f"got {found_states!r}"
    )


def test_chain_link_labels_align_across_sub_chain_alerts():
    """The 6 sub-chain alerts (3 cli-mirror + 3 mirror-domain) MUST
    carry the canonical chain_link label values. Drift = Grafana
    filters silently exclude one sub-chain."""
    by_name = {r["alert"]: r for r in _alert_rules()}
    cli_mirror_alerts = {
        "M060CliMirrorChainDegraded",
        "M060CliMirrorChainBroken",
        "M060CliMirrorObserverSilent",
    }
    mirror_domain_alerts = {
        "M060MirrorDomainChainDegraded",
        "M060MirrorDomainChainBroken",
        "M060MirrorDomainObserverSilent",
    }
    for name in cli_mirror_alerts:
        assert by_name[name]["labels"].get("chain_link") == "cli-mirror", (
            f"alert {name!r} chain_link label drift"
        )
    for name in mirror_domain_alerts:
        assert by_name[name]["labels"].get("chain_link") == "mirror-domain", (
            f"alert {name!r} chain_link label drift"
        )


def test_grafana_dashboards_carry_300_red_threshold():
    """Both M060 sub-chain Grafana dashboards render the observer-
    age red threshold at 300s — same as the alert. Drift here =
    the operator sees the dashboard turn red at a different age
    than the alert pages."""
    dashboard_paths = [
        REPO_ROOT / "docs" / "observability" / "dashboards" / "sovereign-os-m060-cli-mirror.json",
        REPO_ROOT / "docs" / "observability" / "dashboards" / "sovereign-os-m060-mirror-domains.json",
    ]
    for path in dashboard_paths:
        data = json.loads(_read(path))
        red_300_found = False
        for panel in data["panels"]:
            if "observer age" not in panel.get("title", "").lower():
                continue
            steps = (
                panel.get("fieldConfig", {})
                .get("defaults", {})
                .get("thresholds", {})
                .get("steps", [])
            )
            for s in steps:
                if s.get("color") == "red" and s.get("value") == STALE_AGE_SECS:
                    red_300_found = True
                    break
            if red_300_found:
                break
        assert red_300_found, (
            f"Grafana dashboard {path.name} missing 300s red threshold "
            f"on observer-age panel"
        )


def test_runbook_sections_reference_observer_silent_alerts():
    """The deployment-guide MUST have runbook sections for both
    observer-silent alerts. Locked here as a cross-surface
    integrity check (per-alert runbook coverage is locked
    separately, but THIS test catches the gap where one is
    documented + the other isn't)."""
    guide = _read(
        REPO_ROOT / "docs" / "operator" / "m060-deployment-guide.md"
    )
    for alert in ("M060CliMirrorObserverSilent", "M060MirrorDomainObserverSilent"):
        assert f"#### {alert}" in guide, (
            f"deployment guide missing #### runbook section for {alert!r}"
        )


def test_partner_repo_selfdef_stale_age_const_matches():
    """Cross-repo opt-in: when $SELFDEF_REPO_ROOT points at a
    selfdef checkout, verify selfdef-api's STALE_AGE_SECS const
    equals our canonical value. Skipped silently when the env
    var is unset."""
    partner_env = os.environ.get("SELFDEF_REPO_ROOT")
    if not partner_env:
        return
    partner = Path(partner_env)
    health_rs = (
        partner / "crates" / "selfdef-api" / "src" / "m060_health.rs"
    )
    if not health_rs.is_file():
        return
    body = health_rs.read_text()
    # The const is declared like `const STALE_AGE_SECS: u64 = 5 * 60;`
    # or `const STALE_AGE_SECS: u64 = 300;`. Capture the expression.
    m = re.search(
        r"const STALE_AGE_SECS:\s*u64\s*=\s*([^;]+);", body,
    )
    assert m is not None, (
        "selfdef m060_health.rs missing STALE_AGE_SECS const"
    )
    # Eval the Rust-numeric-literal expression (5 * 60 or 300 work as
    # Python expressions too).
    value_expr = m.group(1).strip()
    value = eval(value_expr, {"__builtins__": {}}, {})
    assert value == STALE_AGE_SECS, (
        f"selfdef m060_health.rs STALE_AGE_SECS drift: "
        f"expected {STALE_AGE_SECS}, got {value} (from {value_expr!r})"
    )


def test_master_dashboard_state_class_set_matches_canonical():
    """The master-dashboard banner's `knownStates` list MUST equal
    the canonical 5-state set. JavaScript drift here = the banner
    fails to apply the right CSS class when the api returns a
    legitimately documented state."""
    body = _read(MASTER_DASHBOARD)
    m = re.search(
        r"const knownStates\s*=\s*\[([^\]]+)\];", body,
    )
    assert m is not None, "master-dashboard missing knownStates const"
    states = set(re.findall(r'"([^"]+)"', m.group(1)))
    # The banner's knownStates includes 'unknown' as the unclassified
    # fallback class; the canonical state set does NOT carry it
    # (since the api never emits 'unknown'). Verify the api-emitted
    # states all appear; unknown is a permitted UI-only addition.
    missing = CHAIN_STATES - states
    assert not missing, (
        f"master-dashboard knownStates drift: missing {sorted(missing)!r}"
    )


# --------------------------------------------------------------------
# 8-domain wire-contract lockstep — closes the silent-coverage-drift
# bug class that the D-12 rules + D-16 audit-chain coverage close
# (selfdef 82014d6 + sovereign-os 234a1e0) was driven by. Sister to
# selfdef commit a233057.
# --------------------------------------------------------------------


def test_smoke_domains_match_canonical_set():
    """The sovereign-os m060-smoke.py DOMAINS tuple MUST contain
    all 8 canonical D-NN IDs from the M060 wire contract. Drift
    means the smoke diagnostic skips a domain the selfdef producer
    publishes — exactly the bug class that hid D-12 rules + D-16
    audit-chain coverage gap for several releases."""
    body = _read(SMOKE_SCRIPT)
    # Extract DOMAINS list opening + body.
    m = re.search(r"DOMAINS\s*=\s*\[(.+?)\]\s*\n", body, re.DOTALL)
    assert m is not None, (
        "m060-smoke.py missing DOMAINS tuple"
    )
    found_ids = set(re.findall(r'"(D-\d{2})"', m.group(1)))
    missing = set(CANONICAL_DOMAIN_IDS) - found_ids
    assert not missing, (
        f"m060-smoke.py DOMAINS missing canonical D-NN IDs: "
        f"{sorted(missing)}. The 8-domain M060 wire contract requires "
        f"all of {sorted(CANONICAL_DOMAIN_IDS)} — drift here means "
        f"the smoke diagnostic skips a domain the producer publishes."
    )


def test_dashboard_per_domain_description_lists_8_domains():
    """The mirror-domains dashboard's per-domain-severity panel
    description MUST enumerate all 8 canonical D-NN IDs. Drift
    means operators reading the hover-text won't know which
    domain a per-series line refers to — exactly the visibility
    gap that D-12 + D-16 fell into."""
    data = json.loads(_read(MIRROR_DOMAINS_DASHBOARD))
    panels = data.get("panels", [])
    target = None
    for panel in panels:
        title = panel.get("title", "").lower()
        if "per-domain severity" in title:
            target = panel
            break
    assert target is not None, (
        "mirror-domains dashboard missing per-domain-severity panel"
    )
    desc = target.get("description", "")
    for d_nn in CANONICAL_DOMAIN_IDS:
        assert d_nn in desc, (
            f"per-domain-severity panel description missing canonical "
            f"D-NN ID {d_nn!r}. Operator hovering the panel won't see "
            f"the domain's existence. Description: {desc!r}"
        )


def test_partner_repo_doctor_domains_match():
    """Cross-repo opt-in: when $SELFDEF_REPO_ROOT points at a
    selfdef checkout, verify the selfdef-cli m060_doctor DOMAINS
    array contains all 8 canonical D-NN IDs in canonical order.
    Symmetric with the selfdef-side assertion (in
    selfdef/tests/observability/test_m060_partner_repo_lockstep.py
    `test_selfdef_doctor_domains_match_canonical_set`)."""
    partner_env = os.environ.get("SELFDEF_REPO_ROOT")
    if not partner_env:
        return
    partner = Path(partner_env)
    doctor_rs = (
        partner / "crates" / "selfdef-cli" / "src" / "m060_doctor.rs"
    )
    if not doctor_rs.is_file():
        return
    body = doctor_rs.read_text()
    id_pattern = re.compile(r'Domain\s*\{\s*\n\s*id:\s*"(D-\d{2})"')
    found_ids = tuple(id_pattern.findall(body))
    assert found_ids == CANONICAL_DOMAIN_IDS, (
        f"partner-repo selfdef-cli m060_doctor DOMAINS drift: "
        f"expected {CANONICAL_DOMAIN_IDS} (canonical order), got "
        f"{found_ids}. The doctor verb is the producer-side triage "
        f"surface; reordering or removing a domain silently breaks "
        f"the consumer-side cockpit dashboards."
    )


def test_partner_repo_api_artifact_names_cover_8_d_nn():
    """Cross-repo opt-in: verify the selfdef-api m060_health
    ARTIFACT_NAMES list covers all 8 D-NN + 2 MS007 = 10
    canonical filenames."""
    partner_env = os.environ.get("SELFDEF_REPO_ROOT")
    if not partner_env:
        return
    partner = Path(partner_env)
    health_rs = (
        partner / "crates" / "selfdef-api" / "src" / "m060_health.rs"
    )
    if not health_rs.is_file():
        return
    body = health_rs.read_text()
    m = re.search(
        r"const ARTIFACT_NAMES:\s*&\[&str\]\s*=\s*&\[([^\]]+)\]",
        body, re.DOTALL,
    )
    if m is None:
        return
    found = set(re.findall(r'"([^"]+\.json)"', m.group(1)))
    missing = CANONICAL_API_ARTIFACTS - found
    extra = found - CANONICAL_API_ARTIFACTS
    assert not missing, (
        f"partner-repo selfdef-api ARTIFACT_NAMES missing canonical "
        f"entries: {sorted(missing)}. The 10-artifact wire contract "
        f"requires 8 D-NN-tied files + 2 MS007 cross-cutting."
    )
    assert not extra, (
        f"partner-repo selfdef-api ARTIFACT_NAMES has unknown entries: "
        f"{sorted(extra)}. If a new mirror artifact was added, this "
        f"test's CANONICAL_API_ARTIFACTS must be bumped in the same "
        f"commit (cross-repo coordinated change)."
    )
    assert len(found) == 10, (
        f"partner-repo selfdef-api ARTIFACT_NAMES must have exactly 10 "
        f"entries (8 D-NN + 2 MS007); got {len(found)}"
    )
