"""Layer 1 lint — every emitted ``sovereign_os_*`` metric has an
observability HOME, or a justified info-tier exemption.

Sister to ``test_metric_inventory_lockstep.py`` (code -> inventory README)
and ``test_dashboard_metrics_lockstep.py`` (dashboard -> emitter). Those
lock DOCUMENTATION coverage. This locks OPERATOR-SURFACE coverage: a metric
the source tree emits MUST be reachable by an operator either as a
Prometheus alert (it pages), a Grafana dashboard panel (it's visualised), a
recording rule (it's pre-aggregated), OR be on the explicit info-tier
exemption list below with a stated reason.

This is the P4 verification gate for observability: it catches the silent
"I added a metric but it pages/charts NOWHERE" regression — exactly the gap
that left the OS's own friction-audit / perimeter / ZFS / backup / security
/ thermal / power / OOM health metrics scraped-but-unalerted until
``sovereign-os-health.rules.yml`` landed. A NEW emitted metric that is
neither homed nor exempt fails here, forcing a deliberate
alert-vs-dashboard-vs-info decision.

Run: ``pytest -xq tests/lint/test_metric_observability_coverage.py``
"""

from __future__ import annotations

import pathlib
import re

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
EMIT_ROOTS = [REPO_ROOT / "scripts"]
ALERTS_DIR = REPO_ROOT / "config" / "prometheus" / "alerts"
RULES_DIR = REPO_ROOT / "config" / "prometheus" / "rules"
DASH_DIR = REPO_ROOT / "docs" / "observability" / "dashboards"

# Emitter patterns — kept in lockstep with
# test_metric_inventory_lockstep.py::_emitted_metric_names so the two gates
# agree on the emitted-metric set. A metric is "emitted" if it appears as an
# emit_metric call site, an emit_metric_set arg line, a # HELP/# TYPE line, or
# a Python _emit_metric("...") call — NOT as an arbitrary substring (label
# values would inflate the set).
_EMIT_PATTERNS = [
    re.compile(r"emit_metric\s+(sovereign_os_[a-z][a-z0-9_]*)\b"),
    re.compile(r"\"(sovereign_os_[a-z][a-z0-9_]*)\s+\$?\{?"),
    re.compile(r"'(sovereign_os_[a-z][a-z0-9_]*)\s"),
    re.compile(r"#\s+(?:HELP|TYPE)\s+(sovereign_os_[a-z][a-z0-9_]*)\b"),
    re.compile(r"_?emit_metric\(\s*[\"'](sovereign_os_[a-z][a-z0-9_]*)[\"']"),
]

# Tokens that look like metric names but are not (bash trap names, etc.).
KNOWN_NON_METRICS = {
    "sovereign_os_trap_err",  # bash trap handler in common.sh
}

# ---------------------------------------------------------------------------
# Info-tier exemptions — emitted families that are deliberately NOT paged on.
# Each is a (regex, reason) over the metric name. Keep these to telemetry /
# usage / housekeeping signals; a real health/failure signal must get a real
# alert or dashboard panel, not an exemption. Prefix patterns keep the list
# short — but every pattern MUST match at least one emitted metric (the
# stale-pattern guard below enforces that).
# ---------------------------------------------------------------------------
EXEMPT_PATTERNS: list[tuple[str, str]] = [
    (r"^sovereign_os_operator_[a-z0-9_]+_(api_request|query)_total$",
     "operator-surface usage counter (request/query volume); aggregate usage "
     "telemetry, not a paging health signal — visualised, not alerted."),
    (r"^sovereign_os_build_pipeline_[a-z0-9_]+$",
     "build-time telemetry emitted DURING image build (steps/duration); not a "
     "runtime-scraped health signal."),
    (r"^sovereign_os_gpu_power_[a-z0-9_]+$",
     "GPU power gauge (draw/limit/deviance); dashboard-tier telemetry — the "
     "paging signals are SovereignOsThermalCritical + the power-shutdown guard."),
    (r"^sovereign_os_gpu_sustained_draw_warning$",
     "GPU sustained-draw warning gauge; overlaps the thermal + power-shutdown "
     "paging paths — dashboard-tier, not separately paged."),
    (r"^sovereign_os_power_(estimated_load_watts|headroom_watts|utilization_pct)$",
     "power-budget gauge; dashboard-tier — the critical power path pages via "
     "SovereignOsPowerShutdownGuardFired / SovereignOsPowerUpsCritical."),
    (r"^sovereign_os_wattage_heat_trend_[a-z0-9_]+$",
     "wattage/heat trend gauge; dashboard-tier trend telemetry — thermal "
     "paging is SovereignOsThermalCritical."),
    (r"^sovereign_os_memory_(available_pct|swap_used_pct|psi_[a-z0-9_]+|pressure_verdict)$",
     "memory-pressure gauge; dashboard-tier + the sovereign-telemetry PSI "
     "alert — the critical memory path pages via SovereignOsMemoryOomKills."),
    (r"^sovereign_os_models_catalog_[a-z0-9_]+$",
     "model-catalog inventory gauge (counts/bytes/last-run); dashboard-tier "
     "inventory state, not a health signal."),
    (r"^sovereign_os_meta_alert(s)?_[a-z0-9_]+$",
     "alerts-check META-counter (the alert engine's own derived-alert tally); "
     "paging on it would be circular — surfaced on the meta-observability panel."),
    (r"^sovereign_os_log_rotation_last_run_timestamp$",
     "log-rotation last-run staleness; low-criticality housekeeping — the "
     "rotated/purged gauges are the operator-facing signal, dashboarded."),
    (r"^sovereign_os_snapshot_created_total$",
     "per-run snapshot-created counter; backup HEALTH pages via "
     "SovereignOsBackupSnapshotStale (the staleness signal)."),
    # --- lifecycle / build / maintenance telemetry (emitted by build, install,
    # and maintenance hooks as step-completion counters + last-run markers;
    # NOT runtime-scraped health gauges) ---
    (r"^sovereign_os_build_step_[a-z0-9_]+$",
     "build-pipeline step telemetry (completion/result + missing-symbol count); "
     "emitted DURING image build, not runtime-scraped health."),
    (r"^sovereign_os_bootstrap_[a-z0-9_]+$",
     "bootstrap step telemetry; build/install-time, not runtime health."),
    (r"^sovereign_os_pre_install_[a-z0-9_]+$",
     "preflight gate telemetry; build/install-time (the gate hard-fails the "
     "install on failure), not a runtime-scraped signal."),
    (r"^sovereign_os_post_install_[a-z0-9_]+$",
     "post-install hook lifecycle telemetry (applied/result counters); "
     "install-time one-shot, not a runtime health gauge."),
    (r"^sovereign_os_ghostproxy_endpoint_install_(result|last_run_timestamp)$",
     "first-boot root-ghostproxy envelope install-hook telemetry (SDD-046; "
     "report-only/installed/install-failed one-shot + last-run marker); the "
     "RUNTIME health signal is the weekly verify pair, paged via "
     "SovereignOsGhostproxyEnvelopeUnhealthy / SovereignOsGhostproxyVerifyStale."),
    (r"^sovereign_os_pulse_[a-z0-9_]+$",
     "pulse build telemetry (bitnet / wasm-aot build counters + timestamps); "
     "build-time, not runtime health."),
    (r"^sovereign_os_models_pull_[a-z0-9_]+$",
     "model-pull maintenance telemetry; operator-triggered lifecycle, not a "
     "runtime health signal."),
    (r"^sovereign_os_network_asymmetric_render_[a-z0-9_]+$",
     "network-render telemetry; config/build-time render counter + timestamp."),
    (r"^sovereign_os_operator_bashrc_install_total$",
     "operator shell-setup counter; one-shot install telemetry."),
    (r"^sovereign_os_dflash_[a-z0-9_]+$",
     "dflash decision/invocation telemetry; operator-tool usage, not health."),
    (r"^sovereign_os_notify_[a-z0-9_]+$",
     "notify-dispatch out-of-band echo telemetry (delivery ok/fail/events + "
     "last-run); the PRIMARY alerting path IS Prometheus (these rules) — notify "
     "is a best-effort push echo, surfaced on the meta-observability panel."),
    (r"^sovereign_os_(memory|power)_sample_last_run_timestamp$",
     "sampling-hook freshness marker; the CRITICAL memory/power signals page "
     "via SovereignOsMemoryOomKills / SovereignOsPowerShutdownGuardFired / "
     "SovereignOsPowerUpsCritical."),
    (r"^sovereign_os_power_shutdown_guard_(advisory_rc|last_run_timestamp)$",
     "power-guard diagnostic telemetry (probe rc + last-run); the paging "
     "signals are SovereignOsPowerShutdownGuardFired / SovereignOsPowerUpsCritical."),
]


def _emitted() -> set[str]:
    out: set[str] = set()
    for base in EMIT_ROOTS:
        if not base.is_dir():
            continue
        for p in base.rglob("*"):
            if p.is_file() and p.suffix in (".sh", ".py"):
                text = p.read_text(errors="ignore")
                for pat in _EMIT_PATTERNS:
                    for name in pat.findall(text):
                        out.add(name)
    return out - KNOWN_NON_METRICS


def _corpus(globs: list[pathlib.Path], pattern: str) -> str:
    return " ".join(
        p.read_text(errors="ignore")
        for d in globs
        if d.is_dir()
        for p in d.glob(pattern)
    )


def _homed(emitted: set[str]) -> set[str]:
    alerts = _corpus([ALERTS_DIR], "*.yml")
    dash = _corpus([DASH_DIR], "*.json")
    rec = _corpus([RULES_DIR], "*.yml")
    blob = alerts + " " + dash + " " + rec
    return {m for m in emitted if m in blob}


def _is_exempt(metric: str) -> bool:
    return any(re.match(pat, metric) for pat, _ in EXEMPT_PATTERNS)


def test_emitters_found():
    em = _emitted()
    assert len(em) > 20, f"expected the sovereign_os_* metric corpus; found {len(em)}"


def test_every_emitted_metric_has_a_home_or_justified_exemption():
    emitted = _emitted()
    homed = _homed(emitted)
    orphans = sorted(m for m in emitted - homed if not _is_exempt(m))
    assert not orphans, (
        "emitted sovereign_os_* metrics with NO observability home (no alert, "
        "no dashboard panel, no recording rule) and not on the info-tier "
        "exemption list:\n  " + "\n  ".join(orphans) + "\n"
        "Give each a Prometheus alert (config/prometheus/alerts/), a dashboard "
        "panel (docs/observability/dashboards/), or — if it is genuinely "
        "info/telemetry — an EXEMPT_PATTERNS entry with a reason in this gate."
    )


def test_no_stale_exemption_patterns():
    """Every exemption pattern must match at least one emitted metric — a
    pattern that matches nothing is dead (the metric was renamed/removed) and
    should be cleaned up so the exemption list can't rot into a rubber stamp."""
    emitted = _emitted()
    stale = [
        pat for pat, _ in EXEMPT_PATTERNS
        if not any(re.match(pat, m) for m in emitted)
    ]
    assert not stale, "exemption patterns matching no emitted metric:\n  " + "\n  ".join(stale)


def test_exemptions_do_not_shadow_an_alerted_metric():
    """Defence-in-depth: an exemption must not cover a metric that IS alerted —
    that would be a contradictory signal (we both page on it and call it
    info-tier). Such a metric should simply not match an exempt pattern."""
    emitted = _emitted()
    alerts = _corpus([ALERTS_DIR], "*.yml")
    alerted = {m for m in emitted if m in alerts}
    contradictory = sorted(m for m in alerted if _is_exempt(m))
    assert not contradictory, (
        "metrics that are BOTH alerted and matched by an info-tier exemption "
        "(remove the exemption coverage):\n  " + "\n  ".join(contradictory)
    )
