"""CoT-registry step ⇄ script existence (E2.M15 P4).

Every CoT routine in scripts/intelligence/cot-registry.py composes a list of
steps, each `["scripts/<path>.py", [<argv>]]`. If a step's script path
doesn't exist, `sovereign-osctl cot run <flow>` fails (or silently skips)
that step — the routine can't actually compose the tool it claims to. This
lint caught 5 dangling step references left behind when scripts were
reorganized/renamed (gpu-wattage → gpu-wattage-catalog, power-profiles →
power/profiles, battery-ladder → power/battery-escalation-ladder,
storage/insights → hardware/fs-insights, lifecycle/drain →
services/dependency-graph). Lock step-script existence so a reorganization
can't silently break a CoT flow again.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COT = REPO_ROOT / "scripts" / "intelligence" / "cot-registry.py"

# Step shape: ["scripts/<path>.py", [ ... ]]
_STEP_SCRIPT = re.compile(r'\[\s*"(scripts/[a-z0-9/_-]+\.py)"\s*,')


def _referenced_scripts() -> set[str]:
    return set(_STEP_SCRIPT.findall(COT.read_text(encoding="utf-8")))


def test_cot_registry_references_scripts():
    refs = _referenced_scripts()
    assert len(refs) >= 8, (
        f"only parsed {len(refs)} CoT step scripts — parser may be broken "
        f"or the registry shrank unexpectedly"
    )


def test_every_cot_step_script_exists():
    refs = _referenced_scripts()
    missing = sorted(r for r in refs if not (REPO_ROOT / r).is_file())
    assert not missing, (
        f"cot-registry references step script(s) that don't exist: "
        f"{missing}. A `cot run <flow>` step that points at a missing "
        f"script can't compose its tool. Update the path (scripts move/"
        f"rename) or remove the step."
    )
