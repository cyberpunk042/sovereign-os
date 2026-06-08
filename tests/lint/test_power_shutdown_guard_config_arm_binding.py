"""power-shutdown-guard config-arm ⇄ power-status advisories binding (SDD-029).

SDD-029 gate 2 contracts TWO arm paths for the graceful-shutdown safety
hook: the `SOVEREIGN_OS_POWER_SHUTDOWN_ARMED=YES` env var OR
`[graceful_shutdown] enabled = true` in power.toml. The config path runs
through power-status.py `advisories --json` → the hook reads
`thresholds.enabled`.

For its whole life the config path was DEAD: cmd_advisories surfaced the
three numeric thresholds but never `enabled`, so the hook's
`thresholds.enabled` lookup was always None → config-armed hosts silently
never auto-shut-down on UPS battery depletion (risking hard power-off /
data loss). The L3 hook test couldn't catch it because it hand-mocks a
probe JSON that DOES include `enabled` — the mock diverged from the real
producer.

This gate binds the REAL producer to the consumer in both directions:
  1. power-status.py advisories --json really emits thresholds.enabled.
  2. enabled reflects the [graceful_shutdown] enabled config value.
  3. the hook actually reads thresholds.enabled (consumer side).
  4. power.toml.example documents the `enabled` option (operator
     discoverability — SDD-029 gate 2).
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
POWER = REPO_ROOT / "scripts" / "hardware" / "power-status.py"
GUARD = REPO_ROOT / "scripts" / "hooks" / "recurrent" / "power-shutdown-guard.sh"
EXAMPLE = REPO_ROOT / "config" / "power.toml.example"


def _advisories(config: Path | None = None) -> dict:
    cmd = [sys.executable, str(POWER)]
    if config is not None:
        cmd += ["--config", str(config)]
    cmd += ["advisories", "--json"]
    cp = subprocess.run(
        cmd, capture_output=True, text=True, timeout=30, cwd=REPO_ROOT,
    )
    assert cp.returncode in (0, 1), (
        f"power-status.py advisories exited {cp.returncode}: {cp.stderr[:300]}"
    )
    return json.loads(cp.stdout)


def test_advisories_emits_thresholds_enabled():
    doc = _advisories()
    thresholds = doc.get("thresholds")
    assert isinstance(thresholds, dict), "advisories has no thresholds object"
    assert "enabled" in thresholds, (
        "power-status.py advisories --json no longer emits thresholds.enabled "
        "— the power-shutdown-guard hook's config-arm gate (SDD-029 gate 2) "
        "reads it; without it, config-based arming silently never works."
    )
    assert thresholds["enabled"] is False, (
        "with no config, thresholds.enabled must default to False (host "
        "warns but never auto-shuts-down until explicitly armed)."
    )


def test_thresholds_enabled_reflects_config():
    with tempfile.NamedTemporaryFile(
        "w", suffix=".toml", delete=False
    ) as f:
        f.write("[graceful_shutdown]\nenabled = true\n")
        cfg = Path(f.name)
    try:
        doc = _advisories(cfg)
        assert doc["thresholds"]["enabled"] is True, (
            "[graceful_shutdown] enabled = true did not surface as "
            "thresholds.enabled=true — config-arm path broken."
        )
    finally:
        cfg.unlink(missing_ok=True)


def test_guard_hook_reads_thresholds_enabled():
    body = GUARD.read_text(encoding="utf-8")
    assert '.get("thresholds", {}).get("enabled")' in body, (
        "power-shutdown-guard.sh no longer reads thresholds.enabled — the "
        "config-arm gate (SDD-029 gate 2) would silently stop working. "
        "Keep the consumer bound to the producer field."
    )


def test_example_documents_enabled_option():
    body = EXAMPLE.read_text(encoding="utf-8")
    assert "[graceful_shutdown]" in body, "missing [graceful_shutdown] block"
    block = body.split("[graceful_shutdown]", 1)[1]
    # Stop at the next section header to scope the assertion.
    block = block.split("\n[", 1)[0]
    assert "enabled" in block, (
        "power.toml.example [graceful_shutdown] block does not document the "
        "`enabled` arm option — operators can't discover SDD-029 gate 2."
    )
