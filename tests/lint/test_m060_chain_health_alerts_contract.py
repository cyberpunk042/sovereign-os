"""M060 chain-health Prometheus alert rules contract.

Locks the alerting surface for the m060-health-api textfile metric
(sovereign_os_operator_m060_health_api_request_total). The rules
fire on the failure modes operators care about — drift between the
rules and the underlying state enumeration would silently mask
real outages.

The textfile metric is emitted by scripts/operator/m060-health-api.py
with labels:
  endpoint = "health" | "state" | "version" | "healthz" | ...
  result   = "online" | "degraded" | "stale" | "offline" | "unreachable" |
             "404" | "405" | "500" | "ok"

Alerts MUST cover all 4 failure states (offline / unreachable /
stale / degraded) + the api-silent case (daemon down or unpolled).
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
RULES_PATH = REPO_ROOT / "config" / "prometheus" / "alerts" / "m060-chain-health.rules.yml"

# The 4 failure states the underlying metric reports + the api-silent case.
# These five alerts query the sovereign_os_operator_m060_health_api_request_total
# textfile metric and represent the CHAIN-WIDE rollup.
REQUIRED_ALERT_NAMES = {
    "M060ChainOffline",
    "M060ChainUnreachable",
    "M060ChainStale",
    "M060ChainDegradedSustained",
    "M060HealthApiSilent",
}

# Per-link alerts for the M060 D-CLI sub-chain (selfdef_cli_mirror_doctor_*
# textfile series shipped by the selfdef-cli-mirror-doctor.timer systemd
# unit). Distinct metric, distinct failure surface — measured separately
# from the chain-wide rollup so operators see which specific link broke.
CLI_MIRROR_ALERT_NAMES = {
    "M060CliMirrorChainDegraded",
    "M060CliMirrorChainBroken",
    "M060CliMirrorObserverSilent",
}

# Per-domain alerts for the M060 chain-wide doctor textfile
# (selfdef_m060_doctor_* series shipped by selfdef-m060-doctor.timer
# in selfdef commit ce58154). Cover all 6 mirror domains in aggregate.
MIRROR_DOMAIN_ALERT_NAMES = {
    "M060MirrorDomainChainDegraded",
    "M060MirrorDomainChainBroken",
    "M060MirrorDomainObserverSilent",
}


def _load_rules() -> dict:
    return yaml.safe_load(RULES_PATH.read_text())


def _all_rules() -> list[dict]:
    doc = _load_rules()
    return [r for g in doc["groups"] for r in g["rules"]]


def test_rules_file_present_and_valid_yaml():
    assert RULES_PATH.is_file()
    doc = _load_rules()
    assert "groups" in doc
    assert isinstance(doc["groups"], list)
    assert len(doc["groups"]) >= 1


def test_rules_file_covers_every_failure_state():
    """The metric labels include 4 failure-state values; missing any
    alert would silently mask that failure mode."""
    rules = _all_rules()
    names = {r["alert"] for r in rules}
    missing = REQUIRED_ALERT_NAMES - names
    assert not missing, f"missing required alerts: {sorted(missing)}"


def test_every_alert_has_required_fields():
    for rule in _all_rules():
        for field in ("alert", "expr", "labels", "annotations"):
            assert field in rule, f"alert {rule.get('alert')!r} missing {field!r}"
        labels = rule["labels"]
        ann = rule["annotations"]
        assert labels.get("severity") in ("warning", "critical"), (
            f"alert {rule['alert']!r} severity must be warning|critical"
        )
        assert labels.get("subsystem") == "m060-mirror-chain"
        assert "summary" in ann and ann["summary"]
        assert "description" in ann and ann["description"]


def test_offline_and_unreachable_are_critical():
    """Offline + unreachable mean the chain is producing no data —
    must be critical severity."""
    by_name = {r["alert"]: r for r in _all_rules()}
    assert by_name["M060ChainOffline"]["labels"]["severity"] == "critical"
    assert by_name["M060ChainUnreachable"]["labels"]["severity"] == "critical"
    assert by_name["M060HealthApiSilent"]["labels"]["severity"] == "critical"


def test_degraded_and_stale_are_warning():
    """Degraded is a legitimate operator-onboarding state; sustained
    degraded becomes a warning. Stale is a stuck loop but artifacts
    still exist (last-known-good rendering) — warning, not critical."""
    by_name = {r["alert"]: r for r in _all_rules()}
    assert by_name["M060ChainDegradedSustained"]["labels"]["severity"] == "warning"
    assert by_name["M060ChainStale"]["labels"]["severity"] == "warning"


def test_chain_state_label_matches_alert_name_intent():
    """Each alert sets chain_state label that must match the
    underlying probe state it triggers on (so consumers can
    group/filter by failure mode)."""
    expected = {
        "M060ChainOffline":           "offline",
        "M060ChainUnreachable":       "unreachable",
        "M060ChainStale":             "stale",
        "M060ChainDegradedSustained": "degraded",
        "M060HealthApiSilent":        "api_silent",
    }
    by_name = {r["alert"]: r for r in _all_rules()}
    for alert, want_state in expected.items():
        got = by_name[alert]["labels"].get("chain_state")
        assert got == want_state, (
            f"alert {alert!r} chain_state label {got!r} != {want_state!r}"
        )


def test_each_chain_alert_expression_references_the_textfile_metric():
    """The 5 chain-wide alerts must query
    sovereign_os_operator_m060_health_api_request_total — drift here
    means the alert silently never fires. The per-link sub-chain
    alerts (cli-mirror, etc.) reference their own textfile metrics
    and are exempt — those are checked separately below."""
    by_name = {r["alert"]: r for r in _all_rules()}
    for name in REQUIRED_ALERT_NAMES:
        assert "sovereign_os_operator_m060_health_api_request_total" in by_name[name][
            "expr"
        ], (
            f"alert {name!r} expr does not reference the canonical chain-wide metric"
        )


def test_critical_alerts_carry_runbook_url():
    """Operators waking up to a 3 AM page need a direct link to the
    runbook in the alert annotation."""
    for rule in _all_rules():
        if rule["labels"].get("severity") == "critical":
            ann = rule["annotations"]
            # Either explicit runbook_url field OR a markdown link in the
            # description pointing at the operator deployment guide.
            has_url = (
                "runbook_url" in ann and ann["runbook_url"].startswith("https://")
            )
            has_md_link = "deployment-guide" in ann.get("description", "")
            assert has_url or has_md_link, (
                f"critical alert {rule['alert']!r} missing runbook_url + "
                f"no deployment-guide link in description"
            )


def test_expressions_reference_endpoint_health_label():
    """All chain-state alerts query the 'health' endpoint specifically
    (not /healthz or /state). The labeling discipline keeps alert noise
    out of liveness probes."""
    by_name = {r["alert"]: r for r in _all_rules()}
    for name in (
        "M060ChainOffline",
        "M060ChainUnreachable",
        "M060ChainStale",
        "M060ChainDegradedSustained",
        "M060HealthApiSilent",
    ):
        assert 'endpoint="health"' in by_name[name]["expr"], (
            f"alert {name!r} expr must filter on endpoint=\"health\""
        )


def test_for_clauses_are_set_to_avoid_single_scrape_blips():
    """Every chain-state alert has a `for` clause to suppress
    single-scrape transients (mid-publish-tick state changes etc.)."""
    by_name = {r["alert"]: r for r in _all_rules()}
    for name in REQUIRED_ALERT_NAMES:
        assert "for" in by_name[name], (
            f"alert {name!r} missing `for:` clause — single-scrape "
            f"blip would page the operator"
        )


def test_rules_file_is_loadable_by_prometheus_promtool_conceptually():
    """Promtool isn't available in this test env, but we can assert
    the structural invariants promtool would check: top-level groups,
    each group has name+rules, each rule has alert+expr OR
    record+expr."""
    doc = _load_rules()
    for group in doc["groups"]:
        assert "name" in group, "every group must have a name"
        assert "rules" in group and isinstance(group["rules"], list)
        for rule in group["rules"]:
            assert ("alert" in rule and "expr" in rule) or (
                "record" in rule and "expr" in rule
            ), f"rule must have alert+expr or record+expr: {rule}"


# ---------------------------------------------------------------------------
# M060 D-CLI sub-chain alerts (driven by selfdef_cli_mirror_doctor_* textfile
# series shipped from selfdef via the selfdef-cli-mirror-doctor.timer)
# ---------------------------------------------------------------------------


def test_cli_mirror_sub_chain_alerts_present():
    """Drift-protection: the M060 D-CLI sub-chain alerts ship in the
    same rules file so a single Prometheus reload covers both
    surfaces. Missing any of these would silently mask the D-CLI
    link's failure modes."""
    rules = _all_rules()
    names = {r["alert"] for r in rules}
    missing = CLI_MIRROR_ALERT_NAMES - names
    assert not missing, f"missing cli-mirror sub-chain alerts: {sorted(missing)}"


def test_cli_mirror_alerts_reference_doctor_textfile_metric():
    """The 3 cli-mirror alerts MUST query the selfdef_cli_mirror_doctor_*
    series the selfdef-cli-mirror-doctor.timer unit emits. Drift here
    means the alert silently never fires even when the chain breaks."""
    by_name = {r["alert"]: r for r in _all_rules()}
    expected_metric = {
        "M060CliMirrorChainDegraded":    "selfdef_cli_mirror_doctor_worst_severity",
        "M060CliMirrorChainBroken":      "selfdef_cli_mirror_doctor_worst_severity",
        "M060CliMirrorObserverSilent":   "selfdef_cli_mirror_doctor_last_run_unix",
    }
    for alert, metric in expected_metric.items():
        assert metric in by_name[alert]["expr"], (
            f"alert {alert!r} expr must reference {metric!r}; got: "
            f"{by_name[alert]['expr']!r}"
        )


def test_cli_mirror_alerts_severity_classification():
    """Degraded = warn (operator action needed but chain still
    serves last-known data); Broken = critical (structural break);
    ObserverSilent = critical (we've lost the signal — can't trust
    the other alerts to fire)."""
    by_name = {r["alert"]: r for r in _all_rules()}
    assert by_name["M060CliMirrorChainDegraded"]["labels"]["severity"] == "warning"
    assert by_name["M060CliMirrorChainBroken"]["labels"]["severity"] == "critical"
    assert by_name["M060CliMirrorObserverSilent"]["labels"]["severity"] == "critical"


def test_cli_mirror_alerts_carry_chain_link_label():
    """The chain_link label lets operators filter the D-CLI sub-chain
    alerts as a group (e.g. "show me all cli-mirror page-worthy
    issues"). All 3 must carry chain_link=cli-mirror."""
    by_name = {r["alert"]: r for r in _all_rules()}
    for name in CLI_MIRROR_ALERT_NAMES:
        link = by_name[name]["labels"].get("chain_link")
        assert link == "cli-mirror", (
            f"alert {name!r} chain_link label {link!r} != 'cli-mirror'"
        )


def test_cli_mirror_alerts_carry_runbook_url_to_producer_guide():
    """The cli-mirror sub-chain runbook lives in the SELFDEF repo
    (producer side) — drift to the sovereign-os deployment-guide
    would point operators at the wrong document."""
    by_name = {r["alert"]: r for r in _all_rules()}
    for name in CLI_MIRROR_ALERT_NAMES:
        url = by_name[name]["annotations"].get("runbook_url", "")
        assert "cyberpunk042/selfdef" in url, (
            f"alert {name!r} runbook_url must point at the selfdef-side "
            f"producer guide; got: {url!r}"
        )
        assert "m060-cockpit-mirror-producers" in url, (
            f"alert {name!r} runbook_url must reference the producer guide; "
            f"got: {url!r}"
        )


def test_cli_mirror_alerts_have_for_clause():
    """Same single-scrape-blip protection: every alert has `for:` so
    a single 60s timer miss doesn't page the operator."""
    by_name = {r["alert"]: r for r in _all_rules()}
    for name in CLI_MIRROR_ALERT_NAMES:
        assert "for" in by_name[name], (
            f"alert {name!r} missing `for:` clause — single-scrape "
            f"blip would page the operator"
        )


def test_mirror_domain_sub_chain_alerts_present():
    """The 3 mirror-domain alerts ship in the same rules file so a
    single Prometheus reload covers both observer textfiles."""
    rules = _all_rules()
    names = {r["alert"] for r in rules}
    missing = MIRROR_DOMAIN_ALERT_NAMES - names
    assert not missing, f"missing mirror-domain sub-chain alerts: {sorted(missing)}"


def test_mirror_domain_alerts_reference_doctor_textfile_metric():
    """The 3 mirror-domain alerts MUST query the selfdef_m060_doctor_*
    series the selfdef-m060-doctor.timer unit emits."""
    by_name = {r["alert"]: r for r in _all_rules()}
    expected_metric = {
        "M060MirrorDomainChainDegraded":  "selfdef_m060_doctor_worst_severity",
        "M060MirrorDomainChainBroken":    "selfdef_m060_doctor_worst_severity",
        "M060MirrorDomainObserverSilent": "selfdef_m060_doctor_last_run_unix",
    }
    for alert, metric in expected_metric.items():
        assert metric in by_name[alert]["expr"], (
            f"alert {alert!r} expr must reference {metric!r}; got: "
            f"{by_name[alert]['expr']!r}"
        )


def test_mirror_domain_alerts_severity_classification():
    """Degraded = warn (operator can clear by onboarding the domain),
    Broken = critical (mirror_export_loop wedge), ObserverSilent =
    critical (signal lost — other alerts cannot fire)."""
    by_name = {r["alert"]: r for r in _all_rules()}
    assert by_name["M060MirrorDomainChainDegraded"]["labels"]["severity"] == "warning"
    assert by_name["M060MirrorDomainChainBroken"]["labels"]["severity"] == "critical"
    assert by_name["M060MirrorDomainObserverSilent"]["labels"]["severity"] == "critical"


def test_mirror_domain_alerts_carry_chain_link_label():
    """chain_link=mirror-domain distinguishes these from the
    cli-mirror sub-chain alerts (chain_link=cli-mirror) so operators
    can filter by chain link."""
    by_name = {r["alert"]: r for r in _all_rules()}
    for name in MIRROR_DOMAIN_ALERT_NAMES:
        link = by_name[name]["labels"].get("chain_link")
        assert link == "mirror-domain", (
            f"alert {name!r} chain_link label {link!r} != 'mirror-domain'"
        )


def test_mirror_domain_alerts_carry_runbook_url_to_producer_guide():
    """Same R10212 boundary: the producer-side runbook lives in
    selfdef; the consumer-side dashboard surfaces it via runbook_url."""
    by_name = {r["alert"]: r for r in _all_rules()}
    for name in MIRROR_DOMAIN_ALERT_NAMES:
        url = by_name[name]["annotations"].get("runbook_url", "")
        assert "cyberpunk042/selfdef" in url, (
            f"alert {name!r} runbook_url must point at selfdef-side guide"
        )


def test_mirror_domain_observer_silent_threshold_is_300_seconds():
    """Same threshold as cli-mirror observer-silent. Sub-chain
    observer cadences are locked at 60s; 5min = 5 missed ticks."""
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["M060MirrorDomainObserverSilent"]["expr"]
    assert "> 300" in expr, (
        f"observer-silent threshold must be exactly 300s; expr: {expr!r}"
    )


def test_cli_mirror_observer_silent_threshold_is_300_seconds():
    """Lock the observer-silent threshold at 5min so the on-call
    contract is explicit: a wedged timer triggers within ~5 missed
    ticks of the 60s cadence. Tighter would noise-alert on transient
    slow scrapes; looser would mask a long-dead observer."""
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["M060CliMirrorObserverSilent"]["expr"]
    assert "> 300" in expr, (
        f"observer-silent threshold must be exactly 300s (5min); expr: {expr!r}"
    )
