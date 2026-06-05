"""MS048 — selfdef-scheduler Prometheus textfile metric contract (sovereign-os
cockpit consumer ↔ selfdef producer cross-repo coherence).

The selfdef Goldilocks Scheduler (`crates/selfdef-scheduler/src/
prometheus_exporter.rs`) renders a textfile-collector .prom file the
sovereign-os cockpit reads at `scripts/cockpit/scheduler-status.py`.
The shared contract is the metric-name set: every metric the cockpit
parses must be present in the producer (else the cockpit reads None /
shows wedged), and every metric the producer emits SHOULD have a
consumer (else the cockpit silently drops it).

This is the sovereign-os mirror of selfdef's
`scripts/test/L1-cross-repo-alert-runbook-binding.sh` — both repos
gate the same cross-repo seams from their own side. Drift detected
on EITHER repo's commit pipeline.

Pure-text shape assertions (no live scheduler, no selfdef daemon, no
runtime metrics scrape — just static cross-repo grep). SKIPs gracefully
when the selfdef repo is not adjacent (env var SOVEREIGN_OS_SELFDEF_REPO
overrides default ../selfdef path).
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CONSUMER = REPO_ROOT / "scripts" / "cockpit" / "scheduler-status.py"

SELFDEF_REPO_DEFAULT = REPO_ROOT.parent / "selfdef"
SELFDEF_REPO = Path(os.environ.get("SOVEREIGN_OS_SELFDEF_REPO", str(SELFDEF_REPO_DEFAULT)))
PRODUCER = SELFDEF_REPO / "crates" / "selfdef-scheduler" / "src" / "prometheus_exporter.rs"

METRIC_NAME_RE = re.compile(r"selfdef_scheduler_[a-z][a-z0-9_]*")


def _extract_metric_names(path: Path) -> set[str]:
    """Pull every selfdef_scheduler_* identifier out of `path`. Drops
    obvious partial-extraction artifacts (names ending in `_` from the
    consumer's docstring comments, and bare `_gpu` from the producer's
    inline comment)."""
    if not path.is_file():
        return set()
    text = path.read_text(encoding="utf-8", errors="replace")
    raw = set(METRIC_NAME_RE.findall(text))
    # Drop trailing-underscore artifacts (e.g. `selfdef_scheduler_decisions_`
    # in a docstring comment) and the bare-prefix `_gpu` (truncated regex
    # match on `_gpu3090_*`).
    return {
        n
        for n in raw
        if not n.endswith("_") and n not in {"selfdef_scheduler_gpu"}
    }


def test_consumer_present():
    """The cockpit consumer file exists where the dashboard expects it."""
    assert CONSUMER.is_file(), f"cockpit scheduler-status not found at {CONSUMER}"


@pytest.mark.skipif(
    not PRODUCER.is_file(),
    reason=f"selfdef repo not adjacent at {SELFDEF_REPO} (set SOVEREIGN_OS_SELFDEF_REPO to override)",
)
def test_consumer_metrics_all_present_in_producer():
    """Every metric the cockpit parses must be present in the selfdef
    producer (else the cockpit reads None / shows the substrate as
    wedged with no real failure)."""
    consumer_metrics = _extract_metric_names(CONSUMER)
    producer_metrics = _extract_metric_names(PRODUCER)

    missing = consumer_metrics - producer_metrics
    assert not missing, (
        f"cockpit references metrics not present in selfdef producer "
        f"(producer-side rename or drop): {sorted(missing)}"
    )


@pytest.mark.skipif(
    not PRODUCER.is_file(),
    reason=f"selfdef repo not adjacent at {SELFDEF_REPO}",
)
def test_producer_metrics_all_consumed_or_explicitly_unused():
    """Every metric the producer emits SHOULD either be consumed by the
    cockpit OR be in the documented `_PRODUCER_ONLY` exempt list (no
    silent drop of newly-published metrics).

    The exempt set is for metrics intentionally not surfaced in the
    cockpit's compact status card (e.g. the per-profile decision
    breakdown, which is in the dashboard's full panel but not the
    cockpit summary)."""
    PRODUCER_ONLY = {
        # selfdef_scheduler_decisions_by_profile — per-profile breakdown
        # surfaces in the full dashboard panel, not the compact cockpit
        # card the scheduler-status consumer renders.
        "selfdef_scheduler_decisions_by_profile",
    }
    consumer_metrics = _extract_metric_names(CONSUMER)
    producer_metrics = _extract_metric_names(PRODUCER)

    silently_dropped = producer_metrics - consumer_metrics - PRODUCER_ONLY
    assert not silently_dropped, (
        f"selfdef producer emits metrics that the cockpit silently "
        f"drops (consumer-side gap): {sorted(silently_dropped)}. "
        f"Either add the metric to scheduler-status.py or add it to "
        f"PRODUCER_ONLY with rationale."
    )


def test_consumer_carries_critical_status_signals():
    """Beyond the cross-repo symmetry, the cockpit MUST carry the four
    operator-critical status signals (textfile_emit_failed,
    substrate_degraded_count, last_run_unix, substrate_healthy). A
    silent drop of any breaks the WEDGED/SILENT/BLIND status ladder
    the cockpit renders. This is the in-doc anchor analogue of the
    selfdef L1 cross-repo gate's Gate 4."""
    text = CONSUMER.read_text()
    for required in (
        "selfdef_scheduler_textfile_emit_failed",
        "selfdef_scheduler_substrate_degraded_count",
        "selfdef_scheduler_last_run_unix",
        "selfdef_scheduler_substrate_healthy",
    ):
        assert required in text, (
            f"cockpit dropped critical status signal {required!r} "
            f"— breaks WEDGED/SILENT/BLIND status ladder"
        )


def test_consumer_status_ladder_intact():
    """The cockpit derives a status string from the parsed metrics
    via derive_card_status; the OK/DEGRADED/PRESSURED/BLIND/SILENT/
    WEDGED ladder is the operator-facing contract per the
    docstring's `## Severity derivation` section. A silent rename or
    drop of any status string breaks the cockpit's alert rendering."""
    text = CONSUMER.read_text()
    for state in ("WEDGED", "SILENT", "BLIND", "DEGRADED", "PRESSURED", "OK"):
        assert f'"{state}"' in text, f"status ladder missing state: {state}"
