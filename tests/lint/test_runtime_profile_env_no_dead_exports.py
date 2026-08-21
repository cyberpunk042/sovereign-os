"""Phase-0 guard (SDD-903): the `trinity profile switch` runtime-profile env
generator must not resurrect DEAD per-tier allocation exports.

`active-runtime-profile-env.sh` is SOURCED only to apply GPU power-state commands
(`GPU_<slot>_COMMAND`). The per-agent model/tier/vram exports the generator used
to emit were consumed by NOTHING — model->card selection flows through
`runtime_profile_override` (scripts/build/lib/runtime-profile.sh), which reads the
active-profile YAML at tier launch (proven by
tests/nspawn/test_runtime_profile_honoring.sh). Those exports were a dead env file
masquerading as the apply path; SDD-903 Phase 0 removed them.

This lint pins that the generator emits ONLY the consumed GPU exports, so the
dead-env class cannot quietly return.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"


def _env_generator_body() -> str:
    """The python heredoc opened right after
    `ENV_FILE="${env_file}" ${PYTHON3} - <<'PYEOF'` — the runtime-profile env
    generator inside `sovereign-osctl`."""
    src = OSCTL.read_text(encoding="utf-8")
    m = re.search(r"ENV_FILE=\"\$\{env_file\}\".*?<<'PYEOF'\n(.*?)\nPYEOF", src, re.S)
    assert m, "could not locate the trinity-profile env generator heredoc"
    return m.group(1)


def test_generator_emits_only_gpu_power_exports():
    """Every `export` the generator appends must be a GPU power-state command —
    the only thing the env file is sourced for."""
    body = _env_generator_body()
    # Match the shell exports the generator appends into the env file, e.g.
    #   lines.append(f'export GPU_{slot.upper()}_COMMAND="{safe}"')
    exports = re.findall(r"export\s+([A-Za-z0-9_{}.()\[\]']+)", body)
    bad = [e for e in exports if "GPU_" not in e]
    assert not bad, (
        f"trinity-profile env generator emits non-GPU exports {bad}; the env "
        "file is sourced only for GPU_<slot>_COMMAND. Per-tier model/tier/vram "
        "exports are dead — model selection flows through runtime_profile_override "
        "(SDD-903 Phase 0)."
    )


def test_no_per_agent_allocation_exports():
    """The dead per-agent allocation-export loop (`export {prefix}_...`,
    `_VRAM_LIMIT_BYTES`, `EXPECTED_POWER_`) must stay removed."""
    body = _env_generator_body()
    for dead in ("{prefix}_", "_VRAM_LIMIT_BYTES", "export EXPECTED_POWER"):
        assert dead not in body, (
            f"dead runtime-profile env export marker {dead!r} re-added to the "
            "generator; keep it out (runtime_profile_override is the model path). "
            "See SDD-903 Phase 0."
        )


def test_generator_documents_the_real_model_path():
    """Anchor the doctrine in the generator so the dead-env class can't quietly
    return: model selection is runtime_profile_override, not this file."""
    body = _env_generator_body()
    assert "runtime_profile_override" in body, (
        "the generator must document that per-tier model selection flows through "
        "runtime_profile_override (not the generated env file)."
    )
