"""DSpark speculative-decoding contract lint — the DFlash (M083) successor.

Locks the `dspark:` block added to
`config/inference/m083-dflash-speculative-decoding.yaml` and its materialization
across the wrapper, the vLLM backend, and the control-systems toggle.

DSpark (DeepSeek, open-sourced 2026-06-27) is speculative decoding built ON TOP
of DFlash: DFlash is the parallel draft BACKBONE; DSpark adds a lightweight
Markov head + domain confidence thresholding, verifies a DSpark-5 block in one
target forward pass via rejection sampling, and is LOSSLESS. Operator directive
(2026-07-13): opt-in like everything, but ON BY DEFAULT for now, surfaced in the
D-21 "Features GPUs" section.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "inference" / "m083-dflash-speculative-decoding.yaml"
REGISTRY = REPO_ROOT / "config" / "control-systems.yaml"
WRAPPER = REPO_ROOT / "scripts" / "inference" / "dspark-wrap.sh"
VLLM = REPO_ROOT / "scripts" / "inference" / "backends" / "vllm.py"
CTL = REPO_ROOT / "scripts" / "inference" / "dspark-ctl.py"
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())["dspark"]


def test_dspark_block_present():
    assert "dspark" in yaml.safe_load(CONTRACT.read_text()), "no dspark: block in the M083 contract"
    assert _c()["successor_to"] == "M083"  # DFlash IS DSpark's draft backbone
    assert _c()["released"] == "2026-06-27"


def test_architecture_lossless_dspark5():
    a = _c()["architecture"]
    assert a["lossless"] is True, "DSpark must be recorded as lossless (rejection-sampling verify)"
    assert "DSpark-5" in a["production_config"]
    assert "Markov head" in a["sequential_head"]
    assert "DFlash" in a["draft_backbone"]


def test_toggle_opt_in_default_on():
    t = _c()["toggle"]
    assert t["opt_in"] is True
    assert t["default_enabled"] is True, "operator: on by default for now"
    assert t["control"] == "dspark-speculative-decoding"


def test_gated_wrapper_exists_and_executable():
    gw = _c()["gated_wrapper"]
    assert gw["script"] == "scripts/inference/dspark-wrap.sh"
    assert WRAPPER.is_file(), f"missing {WRAPPER}"
    import os
    assert os.access(WRAPPER, os.X_OK), "dspark-wrap.sh must be executable"


def test_override_knobs_disable_wins():
    ok = _c()["override_knobs"]
    assert ok["enable"] == "DSPARK_ENABLE_OVERRIDE"
    assert ok["disable"] == "DSPARK_DISABLE_OVERRIDE"
    assert ok["precedence"] == "DISABLE wins when both set"


def test_vllm_backend_binding_is_dspark():
    b = [x["backend"] for x in _c()["backend_bindings"]]
    assert b == ["vllm", "llama_cpp", "transformers"]
    vllm = next(x for x in _c()["backend_bindings"] if x["backend"] == "vllm")
    assert '"method":"dspark"' in vllm["argv"]


def test_graceful_degradation_never_hard_failure():
    gd = _c()["graceful_degradation"]["rule"]
    assert "vanilla decoding" in gd and "never a hard failure" in gd
    assert "DFlash" in gd  # falls back to the DFlash backbone first


def test_panel_surface_is_d21_features_gpu():
    ps = _c()["panel_surface"]
    assert ps["dashboard"] == "d-21-lm-orchestration"
    assert ps["section"] == "Features GPUs"


def test_wrapper_carries_the_knobs():
    src = WRAPPER.read_text()
    for tok in ("DSPARK_ENABLE_OVERRIDE", "DSPARK_DISABLE_OVERRIDE", "DSPARK_BLOCK",
                "num_speculative_tokens", "dspark"):
        assert tok in src, f"dspark-wrap.sh missing {tok!r}"
    # DISABLE must be evaluated before ENABLE in the gating (DISABLE wins)
    assert src.index('if [ -n "${DSPARK_DISABLE_OVERRIDE') < src.index('elif [ -n "${DSPARK_ENABLE_OVERRIDE')


def test_vllm_backend_prefers_dspark():
    src = VLLM.read_text()
    assert '"method": "dspark"' in src, "vLLM backend must emit the dspark speculative-config"
    assert "dspark_draft_model" in src
    # DSpark preferred over DFlash: its branch comes first
    assert src.index("self.dspark_draft_model") < src.index("elif self.dflash_draft_model")


def test_control_systems_toggle_registered():
    systems = yaml.safe_load(REGISTRY.read_text())["systems"]
    d = next((s for s in systems if s["id"] == "dspark-speculative-decoding"), None)
    assert d is not None, "control-systems.yaml missing the dspark-speculative-decoding toggle"
    assert d["kind"] == "toggle"
    assert d["options"] == ["on", "off"]  # quoted → real strings (not YAML on/off booleans)
    assert "d-21-lm-orchestration" in d["applies_to"]


def test_ctl_exists_and_wired_into_osctl():
    import os
    assert CTL.is_file(), f"missing {CTL}"
    assert os.access(CTL, os.X_OK), "dspark-ctl.py must be executable"
    body = OSCTL.read_text()
    assert "dspark)" in body, "sovereign-osctl missing the dspark) dispatch case"
    assert "scripts/inference/dspark-ctl.py" in body, "dspark) must delegate to dspark-ctl.py"


def test_ctl_state_matches_wrapper_precedence():
    """The CLI, the wrapper, and the API must agree: absent file → default-on;
    `enabled = false` → off; the three read the SAME DSPARK_STATE path."""
    src = CTL.read_text()
    assert "DSPARK_STATE" in src and "dspark.toml" in src
    assert "enabled=false" in src.replace(" ", "")  # OFF sentinel the wrapper/api also match
    for verb in ("status", "enable", "disable"):
        assert f'"{verb}"' in src, f"dspark-ctl.py missing the {verb!r} verb"
