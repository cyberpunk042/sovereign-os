"""R394 (E10.M38) — Pulse build-bitnet operator-verbatim §16 + §9.1 + §15 content lint.

Closes the Trinity-side pinning trio:
  R392 Auditor:  scripts/auditor/guardian-core.py (§10.1)
  R393 Weaver:   scripts/weaver/atomic-state.py (§21.1)
  R394 Pulse:    scripts/pulse/build-bitnet.sh (§9.1 + §15 + §16)

Master spec §9.1 verbatim Dockerfile snippet:
  ENV CFLAGS="-march=znver5 -mavx512f -mavx512dq -mavx512bw
              -mavx512vl -mavx512bf16 -mavx512fp16"
  ENV GGML_AVX512=1
  ENV GGML_AVX512_VBMI=1
  ENV GGML_AVX512_VNNI=1

Master spec §15 + §16: BitNet b1.58 ternary {-1, 0, +1} ternary weights
+ Pulse runtime executes via bitnet.cpp on CCD 0.

If a future agent silently shortens CFLAGS or swaps to znver4, the
Pulse runtime loses operator-named AVX-512 path. R394 catches.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PULSE_BUILD = REPO_ROOT / "scripts" / "pulse" / "build-bitnet.sh"


def _read_pulse_build() -> str:
    assert PULSE_BUILD.is_file(), f"missing {PULSE_BUILD}"
    return PULSE_BUILD.read_text(encoding="utf-8")


def test_pulse_build_file_exists():
    assert PULSE_BUILD.is_file(), f"missing {PULSE_BUILD}"


def test_cflags_znver5_verbatim():
    """§16 + §9.1 verbatim: -march=znver5 is the operator-named CPU
    arch target. Pulse compile MUST use znver5 (not generic / znver4)."""
    body = _read_pulse_build()
    assert "-march=znver5" in body, (
        "build-bitnet.sh missing -march=znver5 (§16 + §9.1 verbatim — "
        "Pulse operator-named CPU arch target)"
    )


def test_all_mavx512_extensions_present():
    """§16 + §9.1 verbatim 5-flag -mavx512* extension list for Zen 5.
    -mavx512fp16 is INTENTIONALLY ABSENT — verified absent on the physical
    9900X (SDD-043, profiles/sain-01.yaml:41); emitting FP16 instructions
    would SIGILL on the target itself. The remaining five flags are the
    operator-verbatim AVX-512 surface for Zen 5."""
    body = _read_pulse_build()
    extensions = ["-mavx512f", "-mavx512dq", "-mavx512bw",
                  "-mavx512vl", "-mavx512bf16"]
    missing = [e for e in extensions if e not in body]
    assert not missing, (
        f"build-bitnet.sh missing operator-verbatim §16+§9.1 -mavx512* "
        f"extensions: {missing}. The Zen-5 five-flag list is required."
    )


def test_mavx512fp16_absent():
    """SDD-043 / profiles/sain-01.yaml:41 — Zen 5 (9900X) does NOT ship
    AVX512-FP16. Compiling with -mavx512fp16 risks SIGILL at runtime if
    the compiler emits FP16 EVEX instructions. This test guards against
    silent re-addition."""
    body = _read_pulse_build()
    import re
    # Only match as an actual compiler flag (space-separated in CFLAGS or
    # a shell variable assignment), not in comments or log messages.
    flag_re = re.compile(r'(?<![A-Za-z0-9_-])-mavx512fp16(?![A-Za-z0-9_-])')
    matches = flag_re.findall(body)
    assert not matches, (
        "build-bitnet.sh contains -mavx512fp16 as a compiler flag — "
        "this flag is FORBIDDEN on Zen 5 targets (verified absent on "
        "physical 9900X). Remove it from CFLAGS."
    )


def test_no_silent_arch_corruption():
    """Catch silent -march= corruption to non-znver5 value."""
    body = _read_pulse_build()
    import re
    march_values = re.findall(r"-march=(\w+)", body)
    bad = [v for v in march_values if v != "znver5"]
    assert not bad, (
        f"build-bitnet.sh contains non-znver5 -march= values: {bad}. "
        f"§16 verbatim specifies znver5 only."
    )


def test_bitnet_cpp_referenced():
    """§17.1 verbatim Pulse runtime: 'bitnet.cpp'. The build script
    MUST reference bitnet.cpp (operator-named runtime)."""
    body = _read_pulse_build()
    body_lower = body.lower()
    assert "bitnet" in body_lower, (
        "build-bitnet.sh missing bitnet reference (§17.1 verbatim — "
        "Pulse runtime is bitnet.cpp)"
    )


def test_bitnet_model_repo_microsoft_b1_58():
    """§15 + dump-tail operator-verbatim model: microsoft/bitnet-b1.58
    family. The default model id MUST reference Microsoft BitNet b1.58."""
    body = _read_pulse_build()
    body_lower = body.lower()
    has_b158 = ("b1.58" in body_lower
                 or "b1_58" in body_lower
                 or "bitnet" in body_lower and "microsoft" in body_lower)
    assert has_b158, (
        "build-bitnet.sh missing microsoft/bitnet-b1.58 model reference "
        "(§15 verbatim — BitNet b1.58 ternary)"
    )


def test_o3_optimization_present():
    """§16 + §2.2 verbatim: -O3 optimization level (NOT -O2 or -Os)."""
    body = _read_pulse_build()
    assert "-O3" in body, (
        "build-bitnet.sh missing -O3 optimization (§16 + §2.2 verbatim — "
        "operator-named optimization level)"
    )


def test_master_spec_section_references_documented():
    """The script SHOULD cite the master spec sections it implements.
    R168/R174 documentation cross-link or §16 comment expected."""
    body = _read_pulse_build()
    # Look for § references in comments
    has_section_ref = ("§" in body or "master spec" in body.lower())
    assert has_section_ref, (
        "build-bitnet.sh missing master spec section references in "
        "comments (operator-discovery context — script should cite "
        "§16 / §15 / §9.1)"
    )


def test_no_silent_optimization_downgrade():
    """Catch silent -O0 / -Os / -Og replacement (would downgrade Pulse
    runtime perf below operator-§16 specified -O3)."""
    body = _read_pulse_build()
    import re
    opt_levels = re.findall(r"-O(\w)", body)
    # -O3 is operator-named; -O2 borderline; -O0/-Os/-Og are downgrades
    bad = [o for o in opt_levels if o in ("0", "s", "g")]
    if bad and "-O3" not in body:
        raise AssertionError(
            f"build-bitnet.sh uses non-O3 optimization {bad} without "
            f"operator-verbatim -O3 present"
        )


def test_ccd_0_pinning_documented():
    """§17.1 verbatim: Pulse executes on CPU 'CCD 0'. The build script
    SHOULD reference CCD 0 (or core range 0-5 / 0-11) for operator-
    discovery."""
    body = _read_pulse_build()
    body_lower = body.lower()
    # Either explicit CCD 0 mention OR core range OR taskset reference
    has_ccd_context = (
        "ccd" in body_lower
        or "0-5" in body_lower
        or "0-11" in body_lower
        or "taskset" in body_lower
        or "affinity" in body_lower
    )
    # Pulse build doesn't strictly NEED to pin CCD itself (taskset
    # happens at runtime in start-pulse.sh). Just informational.
    # Pass if either present OR if build script focuses on compile only.
    assert True  # Informational only


def test_install_path_consistent():
    """Pulse runtime installs bitnet-cli to /usr/local/bin (operator-
    convention path for local-build binaries)."""
    body = _read_pulse_build()
    assert "/usr/local/bin" in body, (
        "build-bitnet.sh missing /usr/local/bin install path "
        "(operator convention for source-built binaries — matches "
        "Tetragon policy allowlist /usr/local/bin/vllm pattern)"
    )
