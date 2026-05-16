"""Layer 1 — hook script path resolution. Every profile.hooks.*.script
path referenced from profiles/*.yaml must resolve to a file in
scripts/hooks/."""

from __future__ import annotations

import pathlib

import pytest

try:
    import yaml
except ImportError:
    pytest.skip("python3-yaml not installed", allow_module_level=True)


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def _all_profile_files() -> list[pathlib.Path]:
    return sorted((REPO_ROOT / "profiles").glob("*.yaml"))


@pytest.mark.parametrize("profile_file", _all_profile_files(), ids=lambda p: p.stem)
def test_hook_script_paths_resolve(profile_file):
    """Each hook's script: path (relative to repo root) must exist + be executable."""
    with profile_file.open() as f:
        prof = yaml.safe_load(f)
    hooks = prof.get("hooks") or {}
    for phase, items in hooks.items():
        for hook in items or []:
            script = hook.get("script")
            if not script:
                continue
            full = REPO_ROOT / script
            assert full.is_file(), (
                f"profile {profile_file.stem} phase {phase} hook {hook.get('id')}: "
                f"script {script} does not exist"
            )
            mode = full.stat().st_mode
            assert mode & 0o100, f"{script} not executable"
