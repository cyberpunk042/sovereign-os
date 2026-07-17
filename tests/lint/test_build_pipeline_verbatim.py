"""R405 (E10.M49) — build pipeline operator-verbatim 9-step contract lint.

Extends R387-R404 operational-artifact pinning to the 9-step build
pipeline (scripts/build/01..09-*.sh + orchestrate.sh).

Master spec + operator-verbatim IaC bar:
  > "easily tweakable and configurable and customisation and even via
  >  env vars when needed, or other pre-existing config or temporary
  >  file detected and restarting from there such as if there is has
  >  to be a local tracking of the progress of a build in multi-steps
  >  that can only ever re-happen locally"

The 9-step contract (operator-named via STEPS array in orchestrate.sh):
  01-bootstrap-forge   — install dev tools + tmpfs ramdisk
  02-kernel-fetch      — clone kernel source
  03-kernel-config     — derive .config from active profile
  04-kernel-compile    — make bindeb-pkg (E101 verbatim)
  05-substrate-prepare — substrate-adapter prep (Q-001)
  06-whitelabel-render — whitelabel templates + overlays
  07-image-build       — substrate-driven image build
  08-image-sign        — sign image + bootloader (secure boot)
  09-image-verify      — QEMU smoke test

Cross-step invariants:
  - Each step exports STEP_ID matching its filename
  - Each step uses state_step_start / state_step_complete (resume support)
  - Each step uses state_step_fail with a kebab-case failure reason
  - Each step sources lib/common.sh + lib/observability.sh
  - Each step honors SOVEREIGN_OS_DRY_RUN
  - orchestrate.sh STEPS array matches actual step filenames

Step-specific invariants:
  - 04 references bindeb-pkg (E101 packaging verbatim)
  - 04 references SOURCE_DATE_EPOCH (SDD-019 reproducibility)
  - 08 references secure boot signing (sbverify / signing key)
  - 09 references QEMU smoke test

If a future agent silently:
  - drops STEP_ID export → orchestrate state machine can't track step
  - drops state_step_fail call → failures don't get recorded
  - changes bindeb-pkg to a different packager → breaks E101 verbatim
  - drops SOURCE_DATE_EPOCH → SDD-019 reproducibility silently breaks
…the 9-step pipeline contract silently breaks.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD_DIR = REPO_ROOT / "scripts" / "build"
ORCHESTRATE = BUILD_DIR / "orchestrate.sh"

STEPS_EXPECTED = [
    "01-bootstrap-forge",
    "02-kernel-fetch",
    "03-kernel-config",
    "04-kernel-compile",
    "05-substrate-prepare",
    "06-whitelabel-render",
    "07-image-build",
    "08-image-sign",
    "09-image-verify",
]


def _read_step(step_id: str) -> str:
    p = BUILD_DIR / f"{step_id}.sh"
    assert p.is_file(), f"missing build step: {p}"
    return p.read_text(encoding="utf-8")


def _read_orchestrate() -> str:
    assert ORCHESTRATE.is_file(), f"missing {ORCHESTRATE}"
    return ORCHESTRATE.read_text(encoding="utf-8")


def test_orchestrate_exists():
    assert ORCHESTRATE.is_file(), f"missing {ORCHESTRATE}"


def test_all_nine_build_steps_exist():
    """Master spec verbatim 9-step pipeline: every step ID MUST have
    a corresponding executable script."""
    for step_id in STEPS_EXPECTED:
        p = BUILD_DIR / f"{step_id}.sh"
        assert p.is_file(), f"missing build step script: {p}"


def test_orchestrate_steps_array_matches():
    """orchestrate.sh STEPS array MUST match the operator-verbatim
    9-step pipeline. Drift adds/removes a step silently."""
    body = _read_orchestrate()
    for step_id in STEPS_EXPECTED:
        assert f'"{step_id}"' in body, (
            f"orchestrate.sh STEPS array missing {step_id!r} "
            f"(operator-verbatim 9-step pipeline)"
        )


def test_each_step_exports_matching_step_id():
    """Each step script MUST export STEP_ID matching its filename.
    Drift breaks state-machine resume — orchestrate can't correlate
    step file to state.yaml entry."""
    for step_id in STEPS_EXPECTED:
        body = _read_step(step_id)
        expected = f'STEP_ID="{step_id}"'
        assert expected in body, (
            f"{step_id}.sh missing STEP_ID=\"{step_id}\" export "
            f"(operator-verbatim — drift breaks resume support)"
        )


def test_each_step_uses_state_step_start():
    """Each step MUST call state_step_start (resume contract)."""
    for step_id in STEPS_EXPECTED:
        body = _read_step(step_id)
        assert "state_step_start" in body, (
            f"{step_id}.sh missing state_step_start call "
            f"(operator-verbatim — required for resume tracking)"
        )


def test_each_step_uses_state_step_complete():
    """Each step MUST call state_step_complete on success."""
    for step_id in STEPS_EXPECTED:
        body = _read_step(step_id)
        assert "state_step_complete" in body, (
            f"{step_id}.sh missing state_step_complete call "
            f"(operator-verbatim — completion not recorded = silent rerun)"
        )


def test_dry_run_branches_use_state_step_dry_run_not_complete():
    """A SOVEREIGN_OS_DRY_RUN branch MUST close out with
    state_step_dry_run, never state_step_complete — completing a
    dry-run with the real inputs_hash makes the next REAL run skip the
    step body entirely (resume-state poisoning, found + fixed
    2026-07-17). Checks every step that short-circuits on DRY_RUN."""
    for step_id in STEPS_EXPECTED:
        body = _read_step(step_id)
        if "SOVEREIGN_OS_DRY_RUN" not in body:
            continue  # step has no dry-run branch; orchestrator gates it
        lines = body.splitlines()
        for i, ln in enumerate(lines):
            if "SOVEREIGN_OS_DRY_RUN:-" in ln and not ln.lstrip().startswith("#"):
                # Scan only the dry-run ARM: stop at the else/fi that
                # closes it (the else arm is the real-run path, where
                # state_step_complete is correct).
                branch: list[str] = []
                for nxt in lines[i + 1 : i + 11]:
                    if nxt.strip() in ("else", "fi") or nxt.strip().startswith("elif "):
                        break
                    branch.append(nxt)
                window = "\n".join(branch)
                assert "state_step_complete" not in window, (
                    f"{step_id}.sh dry-run branch calls state_step_complete "
                    f"— must call state_step_dry_run instead (resume-state "
                    f"poisoning: real run would skip the step body)"
                )


def test_each_step_handles_failure_via_state_step_fail():
    """Each step that can fail MUST call state_step_fail with a
    kebab-case reason (operator-discovery: state.yaml shows WHY)."""
    # 01-bootstrap, 02-fetch, 04-compile, 05-substrate, 07-image,
    # 08-sign, 09-verify all have failure paths. 03-config + 06-render
    # may not always have explicit fail paths but they should be there.
    for step_id in STEPS_EXPECTED:
        body = _read_step(step_id)
        assert "state_step_fail" in body, (
            f"{step_id}.sh missing state_step_fail handling "
            f"(operator-discovery — failures need a state.yaml reason)"
        )


def test_each_step_sources_common_and_observability():
    """Each step MUST source lib/common.sh + lib/observability.sh
    (provides log_*, profile_field, emit_metric, etc.)."""
    for step_id in STEPS_EXPECTED:
        body = _read_step(step_id)
        assert "lib/common.sh" in body, (
            f"{step_id}.sh missing 'lib/common.sh' source "
            f"(provides log_info / profile_field — drift breaks step)"
        )
        assert "lib/observability.sh" in body, (
            f"{step_id}.sh missing 'lib/observability.sh' source "
            f"(provides emit_metric / log_step_header — drift loses metrics)"
        )


def test_each_step_honors_dry_run():
    """Each step MUST honor SOVEREIGN_OS_DRY_RUN env var.
    Drift = dry-run silently executes actual work."""
    for step_id in STEPS_EXPECTED:
        body = _read_step(step_id)
        assert "SOVEREIGN_OS_DRY_RUN" in body, (
            f"{step_id}.sh missing SOVEREIGN_OS_DRY_RUN honor "
            f"(operator-verbatim CI/preview safety)"
        )


def test_each_step_emits_a_metric():
    """Each step SHOULD emit at least one Layer B metric
    (SDD-016 verbatim — operator-discovery surface)."""
    for step_id in STEPS_EXPECTED:
        body = _read_step(step_id)
        has_metric = "emit_metric" in body
        assert has_metric, (
            f"{step_id}.sh missing emit_metric call "
            f"(SDD-016 verbatim — Layer B metrics observability)"
        )


# Tokens that mark a success-class metric emission. Two styles coexist in the
# pipeline: direct `result="success"` labels and helper-fn dispatch like
# `emit_substrate_metric success` (where result="$1"). 07 also uses other
# success-ish kebab results. Match both.
_SUCCESS_RE = re.compile(r'result=\\?"success\\?"|_metric\s+success')
_FAIL_RE = re.compile(r'result=\\?"fail\\?"|_metric\s+fail')


def test_each_step_has_success_fail_metric_symmetry():
    """Fail-symmetry invariant: a step that can emit a result="success"
    metric MUST also be able to emit result="fail".

    This codifies a recurring observability defect found across the
    pipeline: a build step that calls state_step_fail on its failure
    paths but never emits the corresponding result="fail" metric. The
    state machine then records WHY in state.yaml, but the Prometheus /
    textfile series `build_step_<x>_total` shows ONLY result="success"
    (or "dry-run") — so an operator dashboard alerting on
    `...{result="fail"}` never fires, and a failed build is invisible as
    the mere ABSENCE of a success sample (indistinguishable from "the
    step never ran").

    If you can report success with a metric, you MUST report failure with
    one. Both the direct `result="fail"` label and the helper-function
    form (`emit_<x>_metric fail`) satisfy the contract.
    """
    for step_id in STEPS_EXPECTED:
        body = _read_step(step_id)
        has_success = bool(_SUCCESS_RE.search(body))
        if not has_success:
            # A step with no success-class metric at all isn't subject to
            # the symmetry rule (it reports purely via state_step_*).
            continue
        has_fail = bool(_FAIL_RE.search(body))
        assert has_fail, (
            f"{step_id}.sh emits a success-class metric but no "
            f'result="fail" / emit_*_metric fail — a failed build would be '
            f"invisible in build_step_*_total (only the absence of a success "
            f"sample). Emit result=\"fail\" on every failure path that calls "
            f"state_step_fail."
        )


# --- Step-specific operator-verbatim invariants ---


def test_step_04_uses_bindeb_pkg_e101():
    """E101 verbatim: kernel packaging via make bindeb-pkg.
    Drift to deb-pkg / rpm / nix silently breaks operator-named
    Debian-archive packaging path."""
    body = _read_step("04-kernel-compile")
    assert "bindeb-pkg" in body, (
        "04-kernel-compile.sh missing bindeb-pkg (E101 verbatim — "
        "operator-named Debian .deb packaging path)"
    )


def test_step_04_propagates_source_date_epoch_sdd_019():
    """SDD-019 verbatim: SOURCE_DATE_EPOCH propagation for kernel
    reproducibility. Drift silently breaks reproducibility."""
    body = _read_step("04-kernel-compile")
    assert "SOURCE_DATE_EPOCH" in body, (
        "04-kernel-compile.sh missing SOURCE_DATE_EPOCH propagation "
        "(SDD-019 verbatim — kernel reproducibility)"
    )


def test_step_04_sets_kbuild_build_timestamp():
    """SDD-019 verbatim: KBUILD_BUILD_TIMESTAMP derived from
    SOURCE_DATE_EPOCH (kernel embeds this; drift = build-time leakage)."""
    body = _read_step("04-kernel-compile")
    assert "KBUILD_BUILD_TIMESTAMP" in body, (
        "04-kernel-compile.sh missing KBUILD_BUILD_TIMESTAMP derivation "
        "(SDD-019 verbatim — reproducibility timestamp pinning)"
    )


def test_step_04_handles_substrate_default_skip():
    """Q18-A: substrate-default profiles skip kernel-compile (Debian
    archive supplies the .deb). Drift = wasteful kernel builds on
    profiles that don't customize the kernel."""
    body = _read_step("04-kernel-compile")
    has_skip = (
        "substrate-default" in body
        and ("skipping" in body.lower() or "skip" in body.lower())
    )
    assert has_skip, (
        "04-kernel-compile.sh missing substrate-default skip handling "
        "(Q18-A — substrate-default profiles use Debian archive .deb)"
    )


def test_step_08_secure_boot_signing():
    """Step 08 MUST handle secure boot signing per profile config.
    Drift losing signing = images don't verify against operator's
    signing key chain."""
    body = _read_step("08-image-sign")
    has_sb = (
        "secure_boot" in body.lower()
        or "secure-boot" in body.lower()
        or "sbsign" in body.lower()
        or "signing" in body.lower()
    )
    assert has_sb, (
        "08-image-sign.sh missing secure boot signing references "
        "(operator-verbatim — image must verify against signing key)"
    )


def test_step_09_qemu_smoke_test():
    """Step 09 MUST run QEMU smoke test (or skip via env var).
    Drift losing QEMU verification = no end-to-end image validation."""
    body = _read_step("09-image-verify")
    has_qemu = "qemu" in body.lower() or "QEMU" in body
    assert has_qemu, (
        "09-image-verify.sh missing QEMU smoke test "
        "(operator-verbatim — image must pass QEMU boot validation)"
    )


def test_step_09_emits_sha256sums():
    """Step 09 SHOULD emit sha256sums.txt (SDD-019 reproducibility
    verification + supply-chain integrity)."""
    body = _read_step("09-image-verify")
    has_sha = (
        "sha256sums" in body.lower()
        or "sha256sum" in body.lower()
    )
    assert has_sha, (
        "09-image-verify.sh missing sha256sums emission "
        "(SDD-019 verbatim — image integrity hashes)"
    )


# --- Cross-pipeline invariants ---


def test_step_order_is_strict_monotonic():
    """Step prefix numbers 01..09 MUST be strictly monotonic.
    Drift introduces ambiguity in orchestrate.sh STEPS ordering."""
    actual_files = sorted(p.name for p in BUILD_DIR.glob("0?-*.sh"))
    expected = [f"{s}.sh" for s in STEPS_EXPECTED]
    assert actual_files == expected, (
        f"build step files don't match operator-verbatim order: "
        f"expected {expected}, got {actual_files}"
    )


def test_orchestrate_documents_iac_bar():
    """orchestrate.sh MUST document the operator-verbatim IaC bar in
    its header (operator-discovery: a reader sees WHY orchestrate
    exists). Drift removes the verbatim mandate from the script that
    embodies it."""
    body = _read_orchestrate()
    has_iac = (
        "easily tweakable" in body.lower()
        or "iac bar" in body.lower()
        or "operator-verbatim" in body.lower()
        or "easily tweakable and configurable" in body.lower()
    )
    assert has_iac, (
        "orchestrate.sh missing operator-verbatim IaC bar reference "
        "(sacrosanct — drift removes the WHY from the driver)"
    )


def test_no_step_kebab_case_drift():
    """STEP_ID names MUST stay kebab-case (NN-lower-with-dashes).
    Drift to camelCase or snake_case breaks state.yaml key parsing."""
    pattern = re.compile(r'^STEP_ID="(0[1-9]-[a-z][a-z0-9-]*)"$', re.M)
    for step_id in STEPS_EXPECTED:
        body = _read_step(step_id)
        m = pattern.search(body)
        assert m, (
            f"{step_id}.sh STEP_ID not in kebab-case 'NN-lower-with-dashes' "
            f"format — drift breaks state-machine key parsing"
        )
        assert m.group(1) == step_id, (
            f"{step_id}.sh STEP_ID={m.group(1)!r} doesn't match filename "
            f"{step_id!r} — silent state-machine drift"
        )
