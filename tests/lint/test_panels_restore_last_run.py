"""A page reload must show the LAST run's log, not an empty console.

Operator, 2026-07-26: "even if the last build is already finished, I should see
its logs as the last loaded run and not an empty build as I refresh the page,
same in the flash page."

Both panels detach their run from the request: the child writes to a log file and
a status file, so /api/run/attach replays the whole log and /api/run/status
reports done + exit_code. But the CLIENTS only restored a run that was still
RUNNING (`if (!st.running) return;`), so refreshing after a build finished — or
failed — wiped the console the operator was reading, including the error that
explained the failure. Losing a failed build's output is the expensive case:
the log is the only record outside root-owned /root/.sovereign-os/log.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD_WEBAPP = REPO_ROOT / "webapp" / "build-configurator" / "index.html"
FLASH_WEBAPP = REPO_ROOT / "webapp" / "flash" / "index.html"
BUILD_API = REPO_ROOT / "scripts" / "operator" / "build-configurator-api.py"
FLASH_API = REPO_ROOT / "scripts" / "operator" / "flash-api.py"

PANELS = ((BUILD_WEBAPP, BUILD_API), (FLASH_WEBAPP, FLASH_API))


def test_status_endpoints_expose_what_a_finished_run_needs():
    """done/exit_code/log_bytes must be reported, not just `running`."""
    for api in (BUILD_API, FLASH_API):
        body = api.read_text(encoding="utf-8")
        for field in ('"done"', '"exit_code"', '"log_bytes"'):
            assert field in body, f"{api.name}: /api/run/status must report {field}"


def test_panels_replay_a_finished_run_on_load():
    """The client must act on a finished run, not bail out of it."""
    for webapp, _ in PANELS:
        html = webapp.read_text(encoding="utf-8")
        assert "log_bytes" in html, (
            f"{webapp.parent.name}: the page must consult log_bytes to decide "
            "whether a previous run left anything to show"
        )
        assert "last run, reloaded" in html, (
            f"{webapp.parent.name}: a replayed run must be LABELLED as the last "
            "run, so it is never mistaken for a live one"
        )
        assert "exit_code" in html, (
            f"{webapp.parent.name}: the replayed run must show its verdict"
        )


def test_no_panel_bails_out_on_a_finished_run():
    """The exact early-return that discarded the log must not come back."""
    flash = FLASH_WEBAPP.read_text(encoding="utf-8")
    assert "if (!st || !st.running) return;" not in flash, (
        "flash panel: this early return threw away every finished run's log"
    )
    build = BUILD_WEBAPP.read_text(encoding="utf-8")
    # the build panel's restoreRun must have a branch for the NOT-running case
    fn = build[build.index("function restoreRun()"):]
    fn = fn[:fn.index("\nif (document.readyState")]
    assert "s.running" in fn and "log_bytes" in fn, (
        "build panel: restoreRun must handle both the running and finished cases"
    )
    # and it must not scroll the operator to the top of a long log
    assert "scrollHeight" in fn, (
        "a replayed log must land on the OUTCOME, not on the first line"
    )
