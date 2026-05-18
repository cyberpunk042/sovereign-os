"""R418 (E10.M62) — build/lib/* infrastructure contract lint.

Extends R387-R417 operational-artifact pinning to:
  scripts/build/lib/common.sh         (log_* + require_* + profile_field + confirm)
  scripts/build/lib/observability.sh  (SDD-016 metric emission)
  scripts/build/lib/state.sh          (state-machine resume support)
  scripts/build/lib/logging.sh        (structured JSONL logging)
  scripts/build/lib/runtime-profile.sh
  scripts/build/lib/selfdef-tune.sh

These libs are the infrastructure that all the prior lints (R397-R417)
depend on:
  - emit_metric — the function R412 + many others assert exists in hooks
  - require_root — the function R411 asserts is called
  - profile_field — the function used by every config-reading hook
  - state_step_start / _complete / _fail — used by R405 + R408
  - confirm — used by R411 decommission hooks

If a future agent silently:
  - renames emit_metric (e.g., to write_metric) = ALL hooks that
    invoke emit_metric break at runtime; lint family stays green
    because they only check that "emit_metric" appears in hook source
  - drops the source-guard on observability.sh = double-sourcing
    breaks bash assoc arrays + leaks env vars
  - changes profile_field signature = profile-driven hooks read wrong
    fields silently
…the lint family's foundation silently breaks.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "scripts" / "build" / "lib"

COMMON = LIB_DIR / "common.sh"
OBSERVABILITY = LIB_DIR / "observability.sh"
STATE = LIB_DIR / "state.sh"
LOGGING = LIB_DIR / "logging.sh"
RUNTIME_PROFILE = LIB_DIR / "runtime-profile.sh"
SELFDEF_TUNE = LIB_DIR / "selfdef-tune.sh"


def _read(p: Path) -> str:
    assert p.is_file(), f"missing {p}"
    return p.read_text(encoding="utf-8")


# --- Structural ---


def test_all_six_libs_exist():
    for p in (COMMON, OBSERVABILITY, STATE, LOGGING, RUNTIME_PROFILE, SELFDEF_TUNE):
        assert p.is_file(), f"build lib missing: {p}"


# --- common.sh contract (the foundation other R lints depend on) ---


def test_common_defines_require_root():
    body = _read(COMMON)
    assert re.search(r"^require_root\(\)", body, re.M), (
        "common.sh missing require_root() function "
        "(R411 lifecycle hooks assert callers invoke it)"
    )


def test_common_defines_require_command():
    body = _read(COMMON)
    assert re.search(r"^require_command\(\)", body, re.M), (
        "common.sh missing require_command() (used by start scripts)"
    )


def test_common_defines_require_file_and_dir():
    body = _read(COMMON)
    assert re.search(r"^require_file\(\)", body, re.M), (
        "common.sh missing require_file()"
    )
    assert re.search(r"^require_dir\(\)", body, re.M), (
        "common.sh missing require_dir()"
    )


def test_common_defines_profile_field():
    """profile_field is invoked by 11+ hooks (zfs-arc-clamp,
    network-vlan-config, friction-audit-spec, etc.). Drift = mass
    silent breakage."""
    body = _read(COMMON)
    assert re.search(r"^profile_field\(\)", body, re.M), (
        "common.sh missing profile_field() function — 11+ hooks "
        "depend on it for YAML path resolution"
    )


def test_common_defines_load_profile():
    body = _read(COMMON)
    assert re.search(r"^load_profile\(\)", body, re.M), (
        "common.sh missing load_profile() function (every profile-"
        "aware hook calls this)"
    )


def test_common_defines_confirm():
    """confirm() is called by R411 decommission hooks. Drift renaming
    it = decommission hooks silently fail with 'confirm: command not
    found' = operator types 'YES' and nothing happens."""
    body = _read(COMMON)
    assert re.search(r"^confirm\(\)", body, re.M), (
        "common.sh missing confirm() function — R411 decommission "
        "hooks depend on it for interactive YES/no prompt"
    )


def test_common_defines_err_trap():
    """Bash err trap function for structured error reporting on
    unexpected failures."""
    body = _read(COMMON)
    has_trap = (
        re.search(r"__sovereign_os_trap_err\(\)", body)
        or "trap " in body
    )
    assert has_trap, (
        "common.sh missing err trap (structured error reporting on "
        "unexpected pipeline failures)"
    )


# --- observability.sh contract (SDD-016 metric emission) ---


def test_observability_defines_emit_metric():
    """emit_metric is the function every R-arc hook expects. Drift
    renaming it = entire telemetry surface breaks silently."""
    body = _read(OBSERVABILITY)
    assert re.search(r"^emit_metric\(\)", body, re.M), (
        "observability.sh missing emit_metric() — operator-named "
        "SDD-016 entry point; renaming breaks ALL telemetry"
    )


def test_observability_defines_emit_metric_set():
    """emit_metric_set is the bulk variant used by R412 recurrent
    hooks (alerts-check, zfs-scrub, tetragon-policy-verify, etc.)."""
    body = _read(OBSERVABILITY)
    assert re.search(r"^emit_metric_set\(\)", body, re.M), (
        "observability.sh missing emit_metric_set() — recurrent "
        "hooks depend on this for bulk metric writes"
    )


def test_observability_has_source_guard():
    """Double-sourcing observability.sh would re-execute initialization
    and potentially break bash assoc arrays / env state. Source guard
    is required."""
    body = _read(OBSERVABILITY)
    has_guard = (
        "__SOVEREIGN_OS_OBSERVABILITY_LIB_SOURCED" in body
        or "_OBSERVABILITY_SOURCED" in body
    )
    assert has_guard, (
        "observability.sh missing source-guard (double-source breaks "
        "bash state)"
    )


def test_observability_writes_to_textfile_collector():
    """SDD-016 verbatim contract: Prometheus textfile collector path.
    Drift to /var/log or similar = node_exporter can't scrape."""
    body = _read(OBSERVABILITY)
    assert "node_exporter/textfile_collector" in body, (
        "observability.sh missing node_exporter/textfile_collector "
        "path (SDD-016 verbatim Prometheus contract)"
    )


def test_observability_uses_atomic_write():
    """SDD-016 verbatim: atomic tempfile + rename (no file locking).
    Drift to direct write = partial reads by scraper = bogus metrics."""
    body = _read(OBSERVABILITY)
    has_atomic = (
        "tempfile" in body.lower()
        or "mv " in body  # tempfile + mv = atomic
        or "rename" in body.lower()
        or ".tmp" in body
    )
    assert has_atomic, (
        "observability.sh missing atomic-write pattern (SDD-016 "
        "verbatim — drift = scraper reads partial files)"
    )


def test_observability_honors_disable_env():
    """Operator-discoverable env knob: SOVEREIGN_OS_METRICS_DISABLE=1
    skips all writes (useful for CI / read-only filesystems)."""
    body = _read(OBSERVABILITY)
    assert "SOVEREIGN_OS_METRICS_DISABLE" in body, (
        "observability.sh missing SOVEREIGN_OS_METRICS_DISABLE handle "
        "(operator-discoverable CI escape hatch)"
    )


def test_observability_honors_dry_run():
    body = _read(OBSERVABILITY)
    assert "SOVEREIGN_OS_DRY_RUN" in body, (
        "observability.sh missing SOVEREIGN_OS_DRY_RUN handling"
    )


def test_observability_honors_telemetry_sink():
    """Profile-driven: profile.observability.telemetry_sink controls
    whether metrics are emitted at all (operator-named per-profile
    knob; drift = always emits regardless of profile)."""
    body = _read(OBSERVABILITY)
    assert "telemetry_sink" in body, (
        "observability.sh missing telemetry_sink profile field "
        "(operator-named per-profile metric-emission gate)"
    )


def test_observability_iac_bar_documented():
    """Operator's IaC bar verbatim in header (sacrosanct evidence
    that this lib implements the operator-named contract)."""
    body = _read(OBSERVABILITY)
    has_iac = (
        "observable and operable" in body
        or "observable_and_operable" in body
    )
    assert has_iac, (
        "observability.sh missing operator-verbatim 'observable and "
        "operable' IaC bar reference (sacrosanct framing — drift "
        "loses the WHY)"
    )


# --- state.sh contract (resume support — R405 build pipeline) ---


def test_state_defines_step_lifecycle_functions():
    """R405 9-step pipeline asserts state_step_start / _complete /
    _fail are called. They MUST exist in state.sh."""
    body = _read(STATE)
    for fn in ("state_step_start", "state_step_complete", "state_step_fail"):
        assert re.search(rf"^{re.escape(fn)}\(\)", body, re.M), (
            f"state.sh missing {fn}() — R405 build pipeline depends on it"
        )


def test_state_defines_should_run():
    """state_step_should_run gates idempotent skip via inputs_hash."""
    body = _read(STATE)
    assert re.search(r"^state_step_should_run\(\)", body, re.M), (
        "state.sh missing state_step_should_run() — idempotent skip gate"
    )


def test_state_defines_inputs_hash():
    """state_inputs_hash computes the hash that gates skip/run.
    Drift to a non-deterministic hash = step re-runs every invocation
    (or skips when it shouldn't)."""
    body = _read(STATE)
    assert re.search(r"^state_inputs_hash\(\)", body, re.M), (
        "state.sh missing state_inputs_hash() function"
    )


# --- selfdef-tune.sh + runtime-profile.sh ---


def test_selfdef_tune_exists_and_sources_cleanly():
    """Cross-repo integration point: selfdef tuning lib. R286 closed
    Q-019 with cross-repo dispatch via this lib."""
    body = _read(SELFDEF_TUNE)
    # Should reference 'selfdef' somewhere (operator-named binding)
    assert "selfdef" in body.lower(), (
        "selfdef-tune.sh doesn't reference 'selfdef' (drift = lib "
        "exists but lost cross-repo binding context)"
    )


def test_runtime_profile_defines_override():
    """runtime_profile_override is called by start-pulse.sh + start-
    logic-engine.sh + start-oracle-core.sh (R402). Drift renaming it
    = all 3 Trinity start scripts break."""
    body = _read(RUNTIME_PROFILE)
    assert re.search(r"^runtime_profile_override\(\)", body, re.M), (
        "runtime-profile.sh missing runtime_profile_override() — "
        "R402 Trinity start scripts depend on it"
    )


def test_runtime_profile_defines_log_active():
    """runtime_profile_log_active prints the active runtime profile
    for operator-discovery (which §18 profile is in effect)."""
    body = _read(RUNTIME_PROFILE)
    assert re.search(r"^runtime_profile_log_active\(\)", body, re.M), (
        "runtime-profile.sh missing runtime_profile_log_active()"
    )


# --- logging.sh contract ---


def test_logging_defines_log_step_header():
    """log_step_header is called by every step script. Drift renaming
    = all step scripts break."""
    body = _read(LOGGING)
    assert re.search(r"^log_step_header\(\)", body, re.M), (
        "logging.sh missing log_step_header() — every step uses it"
    )


def test_logging_defines_basic_log_levels():
    body = _read(LOGGING)
    for fn in ("log_info", "log_warn", "log_error"):
        assert re.search(rf"^{fn}\(\)", body, re.M), (
            f"logging.sh missing {fn}() — log discipline floor"
        )
