"""R448 (E11.M5) — global-history verb contract lint.

Extends R387-R447 + R443 (osctl help DX) operational-artifact
pinning to:
  scripts/operator/global-history.py
  scripts/sovereign-osctl (global-history dispatch + help text)

Per operator §1g verbatim:
  "Some kind of global history too. tracking things happening, delta,
   differentials... apt changes and operations, or any cli or tool call
   I guess, in the management. more reliable and adapted than simply
   aggregating the .bash_history's."

This ships E11.M5 substantively (3rd feature round after R446 catalog
enrichment + R447 bashrc).

If a future agent silently:
  - drops a source from the 6-source taxonomy = §1g coverage shrinks
  - changes apt log path = system-level history broken
  - drops --since flexibility (ISO + relative 24h/7d) = operator UX gap
…the operator-named §1g surface silently degrades.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GH_PY = REPO_ROOT / "scripts" / "operator" / "global-history.py"
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# --- Structural ---


def test_global_history_script_exists():
    assert GH_PY.is_file(), f"missing {GH_PY}"


def test_global_history_script_executable():
    assert os.access(GH_PY, os.X_OK), (
        f"{GH_PY} not executable"
    )


def test_global_history_has_python3_shebang():
    body = _read(GH_PY)
    assert body.startswith("#!/usr/bin/env python3"), (
        "global-history.py missing python3 shebang"
    )


def test_documents_e11_m5_origin():
    body = _read(GH_PY)
    assert "E11.M5" in body and "§1g" in body, (
        "global-history.py missing E11.M5 + §1g binding"
    )


def test_quotes_operator_verbatim():
    body = _read(GH_PY)
    has_phrases = (
        "delta" in body.lower()
        and "differential" in body.lower()
        and "apt" in body.lower()
        and ".bash_history" in body
    )
    assert has_phrases, (
        "global-history.py missing §1g verbatim phrases "
        "(delta/differential/apt/.bash_history)"
    )


# --- 6-source taxonomy ---


def test_known_sources_set():
    """6 operator-named sources: apt + dpkg + shell + osctl + events
    + modules."""
    body = _read(GH_PY)
    assert "KNOWN_SOURCES" in body, (
        "global-history.py missing KNOWN_SOURCES constant"
    )
    for s in ("apt", "dpkg", "shell", "osctl", "events", "modules"):
        assert f'"{s}"' in body, (
            f"KNOWN_SOURCES missing source {s!r}"
        )


def test_apt_log_path():
    body = _read(GH_PY)
    assert "/var/log/apt/history.log" in body, (
        "global-history.py missing /var/log/apt/history.log path"
    )


def test_dpkg_log_path():
    body = _read(GH_PY)
    assert "/var/log/dpkg.log" in body, (
        "global-history.py missing /var/log/dpkg.log path"
    )


def test_shell_history_path():
    body = _read(GH_PY)
    assert ".bash_history" in body, (
        "global-history.py missing .bash_history path"
    )


def test_source_readers_complete():
    """Each known source has a corresponding reader function."""
    body = _read(GH_PY)
    expected = ["_read_apt", "_read_dpkg", "_read_shell",
                "_read_osctl", "_read_events", "_read_modules"]
    for fn in expected:
        assert f"def {fn}(" in body, (
            f"global-history.py missing {fn}() reader"
        )


def test_source_readers_dispatch_table():
    body = _read(GH_PY)
    assert "SOURCE_READERS" in body, (
        "global-history.py missing SOURCE_READERS dispatch table"
    )


# --- CLI surface ---


def test_supports_recent_verb():
    body = _read(GH_PY)
    assert '"recent"' in body, "global-history.py missing recent verb"


def test_supports_summary_verb():
    body = _read(GH_PY)
    assert '"summary"' in body, "missing summary verb"


def test_supports_sources_verb():
    body = _read(GH_PY)
    assert '"sources"' in body, "missing sources verb"


def test_supports_delta_verb():
    body = _read(GH_PY)
    assert '"delta"' in body, "missing delta verb"


def test_supports_tail_verb():
    """R481 (E11.M5+) — live-tail TUI surface, closes surface-map
    FUTURE waiver 'tui: FUTURE — live-tail history TUI'."""
    body = _read(GH_PY)
    assert '"tail"' in body, "global-history.py missing tail verb"
    assert "def cmd_tail(" in body, (
        "global-history.py missing cmd_tail() function"
    )


def test_tail_verb_has_refresh_loop():
    """tail verb implements a refresh loop (sleep + ANSI clear)
    — that's what makes it a TUI surface vs a one-shot CLI verb."""
    body = _read(GH_PY)
    assert "time.sleep(" in body, (
        "global-history.py tail verb missing refresh loop (time.sleep)"
    )
    assert "\\x1b[2J" in body, (
        "global-history.py tail verb missing ANSI clear-screen "
        "(refresh-flicker hint that this is a TUI surface)"
    )


def test_tail_verb_emits_metric_with_tail_label():
    """Layer B metric labels{verb=tail} so observability aggregates
    the new TUI surface separately from the one-shot verbs."""
    body = _read(GH_PY)
    assert '"tail"' in body and "sovereign_os_operator_global_history_query_total" in body, (
        "global-history.py tail verb must emit query_total metric"
    )


def test_tail_verb_refuses_subsecond_refresh():
    """Operator-discoverable: refresh ≥ 1s; the verb refuses poll-storm."""
    body = _read(GH_PY)
    assert "max(1, int(args.refresh)" in body or "max(1, args.refresh" in body, (
        "global-history.py tail verb missing refresh ≥1s floor"
    )


def test_supports_json_and_human_format():
    body = _read(GH_PY)
    assert "--json" in body and "--human" in body, (
        "global-history.py missing --json/--human flags"
    )


def test_supports_since_relative_and_iso():
    """Operator-discoverable: --since accepts ISO 8601 AND relative
    (24h, 7d, 2w, 1m)."""
    body = _read(GH_PY)
    has_iso = "ISO 8601" in body or "isoformat" in body
    has_relative = re.search(r"24h|7d|2w|1m", body)
    assert has_iso, (
        "global-history.py missing ISO 8601 --since support"
    )
    assert has_relative, (
        "global-history.py missing relative --since support (24h/7d/2w/1m)"
    )


def test_supports_source_filter():
    body = _read(GH_PY)
    assert "--source" in body, (
        "global-history.py missing --source filter"
    )


# --- Operator-environment overrides ---


def test_apt_log_path_env_overridable():
    body = _read(GH_PY)
    assert "SOVEREIGN_OS_GLOBAL_HISTORY_APT_LOG" in body, (
        "global-history.py missing apt log env override"
    )


def test_shell_path_env_overridable():
    body = _read(GH_PY)
    assert "SOVEREIGN_OS_GLOBAL_HISTORY_SHELL" in body, (
        "global-history.py missing shell env override"
    )


# --- Observability ---


def test_emits_layer_b_metric():
    """SDD-016: sovereign_os_operator_global_history_query_total
    {verb,source,result}."""
    body = _read(GH_PY)
    assert "sovereign_os_operator_global_history_query_total" in body, (
        "global-history.py missing query_total metric"
    )


# --- Read-only safety ---


def test_no_destructive_filesystem_ops():
    """global-history.py is read-only. Drift to write/remove =
    operator-discoverable safety violation."""
    body = _read(GH_PY)
    # Allow os.makedirs for metrics dir + tmp.replace for atomic
    # metric write; no other write/remove patterns.
    forbidden = [
        "os.remove(",
        "os.unlink(",
        "shutil.rmtree(",
        "open(.+, 'w')",
        ".write_text(",  # source readers should NEVER write
    ]
    # Enforce the contract: every forbidden destructive op must be ABSENT.
    # `.write_text(` is the single exception — the metric writer — bounded by
    # the ≤1 check below; all others must be zero. (open(.+,'w') is a regex;
    # the rest are literal substrings.)
    for pat in forbidden:
        if pat == ".write_text(":
            continue
        present = bool(re.search(pat, body)) if "(.+" in pat else (pat in body)
        assert not present, (
            f"global-history.py contains forbidden destructive op {pat!r} — "
            "it must stay read-only (operator-discoverable safety violation)"
        )
    # The metric writer uses .write_text + .replace — exempt it
    # via context inspection (only one write_text expected)
    write_count = body.count(".write_text(")
    assert write_count <= 1, (
        f"global-history.py has {write_count} write_text calls "
        f"(expected ≤1 for metric emission only)"
    )


def test_dry_run_supported():
    body = _read(GH_PY)
    assert "SOVEREIGN_OS_DRY_RUN" in body, (
        "global-history.py missing SOVEREIGN_OS_DRY_RUN handling"
    )


# --- osctl integration ---


def test_osctl_dispatches_global_history():
    body = _read(OSCTL)
    assert "global-history)" in body, (
        "sovereign-osctl missing global-history) dispatcher case"
    )
    assert "global-history.py" in body, (
        "sovereign-osctl dispatcher doesn't reference global-history.py"
    )


def test_osctl_help_documents_global_history():
    """R443 DX bar: cmd_help() MUST document global-history
    subcommands."""
    body = _read(OSCTL)
    for sub in ("global-history recent", "global-history summary",
                "global-history sources", "global-history delta",
                "global-history tail"):
        assert sub in body, (
            f"sovereign-osctl help missing {sub!r}"
        )


def test_osctl_help_references_e11_m5():
    body = _read(OSCTL)
    assert "E11.M5" in body, (
        "sovereign-osctl help missing E11.M5 reference"
    )


# --- End-to-end smoke (read sources status) ---


def test_sources_verb_runs_without_error():
    """The sources verb is the safest smoke test (read-only,
    no side effects, runs anywhere)."""
    result = subprocess.run(
        ["python3", str(GH_PY), "sources", "--json"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, (
        f"global-history.py sources --json failed:\n"
        f"  stdout: {result.stdout[:200]}\n"
        f"  stderr: {result.stderr[:200]}"
    )
    import json
    data = json.loads(result.stdout)
    assert "sources" in data, "sources JSON missing 'sources' key"
    assert len(data["sources"]) == 6, (
        f"expected 6 sources, got {len(data['sources'])}"
    )


# --- R487 (E11.M5+) — Grafana dashboard surface ---


GH_DASHBOARD_JSON = (
    REPO_ROOT / "docs" / "observability" / "dashboards"
    / "sovereign-os-global-history.json"
)


def test_dashboard_json_exists():
    """R487 — global-history Grafana dashboard surface (closes surface-
    map FUTURE waiver 'dashboard: FUTURE — Grafana timeline panel')."""
    assert GH_DASHBOARD_JSON.is_file(), (
        f"missing global-history dashboard: {GH_DASHBOARD_JSON}"
    )


def test_dashboard_json_parseable():
    """The dashboard MUST be valid JSON (Grafana refuses invalid JSON
    on import)."""
    import json
    data = json.loads(GH_DASHBOARD_JSON.read_text(encoding="utf-8"))
    assert "panels" in data, "dashboard missing panels"
    assert "title" in data and data["title"], "dashboard missing title"
    assert "uid" in data and data["uid"], "dashboard missing uid"


def test_dashboard_references_global_history_metric():
    """At least one panel MUST query sovereign_os_operator_global_
    history_query_total — otherwise the dashboard isn't visualizing
    the operator-§1g surface."""
    body = GH_DASHBOARD_JSON.read_text(encoding="utf-8")
    assert "sovereign_os_operator_global_history_query_total" in body, (
        "global-history dashboard doesn't reference the Layer B metric"
    )


def test_dashboard_covers_six_sources():
    """Per §1g 6-source registry, dashboard MUST reference all 6
    source labels (apt / dpkg / shell / osctl / events / modules)."""
    body = GH_DASHBOARD_JSON.read_text(encoding="utf-8")
    for src in ("apt", "dpkg", "shell", "osctl", "events", "modules"):
        assert src in body, (
            f"global-history dashboard missing source reference: {src!r}"
        )


def test_dashboard_covers_all_verbs():
    """Dashboard MUST reference all 5 verbs the operator can invoke
    (recent / summary / sources / delta / tail)."""
    body = GH_DASHBOARD_JSON.read_text(encoding="utf-8")
    for verb in ("recent", "summary", "sources", "delta", "tail"):
        assert verb in body, (
            f"global-history dashboard missing verb reference: {verb!r}"
        )


def test_dashboard_quotes_operator_1g_verbatim():
    """Dashboard MUST include the §1g verbatim 'delta, differentials'
    + 'bash_history' anchors — preserves operator-§1g source-of-truth
    on the visual surface."""
    body = GH_DASHBOARD_JSON.read_text(encoding="utf-8")
    assert "delta, differentials" in body, (
        "global-history dashboard missing §1g verbatim 'delta, differentials'"
    )
    assert ".bash_history" in body, (
        "global-history dashboard missing §1g verbatim '.bash_history' anchor"
    )


def test_dashboard_listed_in_readme():
    """README.md MUST list the new dashboard (operator-discoverable
    inventory)."""
    readme = (GH_DASHBOARD_JSON.parent / "README.md").read_text(encoding="utf-8")
    assert "sovereign-os-global-history.json" in readme, (
        "dashboards/README.md missing sovereign-os-global-history.json entry"
    )


def test_dashboard_tagged_sovereign_os():
    """Grafana 'sovereign-os' tag MUST be set — operator's dashboard
    folder filter depends on it."""
    import json
    data = json.loads(GH_DASHBOARD_JSON.read_text(encoding="utf-8"))
    assert "sovereign-os" in (data.get("tags") or []), (
        "global-history dashboard missing sovereign-os tag"
    )
