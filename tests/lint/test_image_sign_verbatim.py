"""R408 (E10.M52) — image-sign secure-boot operator-verbatim SDD-015 lint.

Extends R387-R407 operational-artifact pinning to:
  scripts/build/08-image-sign.sh

SDD-015 (Q-006 resolution) verbatim 3-level enum:
  none   — no signing (dev/throwaway). Step is a no-op.
  shim   — Microsoft-signed shim chains to operator MOK → kernel.
           Step sbsign's vmlinuz + EFI binaries with operator MOK.
  signed — direct sbsign with operator's Platform Key, no shim.
           Step sbsign's everything with PK; falls back to MOK
           with a warning if PK env vars unset.

Operator-supplied keys (NEVER stored in repo — operator's standing
"Operator-supplied keys NEVER in-repo" mandate):
  SOVEREIGN_OS_PK_KEY    Platform Key (preferred for signed)
  SOVEREIGN_OS_PK_CERT   Platform Key cert
  SOVEREIGN_OS_MOK_KEY   MOK private key
  SOVEREIGN_OS_MOK_CERT  MOK certificate

If a future agent silently:
  - hardcodes a key path in the repo = OPERATOR MANDATE VIOLATION
    "Operator-supplied keys NEVER in-repo"
  - drops the 3-level enum case = unknown posture silently accepted
  - drops the sbverify check = signed file might be malformed without
    detection
  - drops the dry-run path = CI/preview runs actually sbsign (and fails
    on hosts without sbsign installed)
…SDD-015 + operator key-mandate silently break.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
IMAGE_SIGN = REPO_ROOT / "scripts" / "build" / "08-image-sign.sh"
MOK_ENROLL = REPO_ROOT / "scripts" / "hooks" / "during-install" / "mok-enroll.sh"


def _read() -> str:
    assert IMAGE_SIGN.is_file(), f"missing {IMAGE_SIGN}"
    return IMAGE_SIGN.read_text(encoding="utf-8")


def test_image_sign_file_exists():
    assert IMAGE_SIGN.is_file(), f"missing {IMAGE_SIGN}"


def test_mok_enroll_exports_pem_cert_for_sbsign():
    """mok-enroll must export SOVEREIGN_OS_MOK_CERT pointing at the PEM cert
    (MOK.crt / ${crt}), NOT the DER (MOK.der / ${der}). 08-image-sign feeds
    SOVEREIGN_OS_MOK_CERT straight to `sbsign --cert`, which requires PEM —
    exporting the DER silently breaks the MOK secure-boot signing path."""
    assert MOK_ENROLL.is_file(), f"missing {MOK_ENROLL}"
    body = MOK_ENROLL.read_text(encoding="utf-8")
    assert re.search(r'SOVEREIGN_OS_MOK_CERT="\$\{crt\}"', body), (
        "mok-enroll.sh must export SOVEREIGN_OS_MOK_CERT=\"${crt}\" (PEM) — "
        "exporting the DER (${der}) breaks sbsign --cert in 08-image-sign"
    )
    assert not re.search(r'SOVEREIGN_OS_MOK_CERT="\$\{der\}"', body), (
        "mok-enroll.sh exports the DER cert to MOK_CERT — sbsign needs PEM"
    )


# --- SDD-015 3-level enum (Q-006 resolution) ---


def test_secure_boot_enum_none_handled():
    body = _read()
    assert " none)" in body or "  none)" in body, (
        "08-image-sign.sh missing 'none' case in secure_boot enum "
        "(SDD-015 Q-006 — none/shim/signed verbatim posture)"
    )


def test_secure_boot_enum_shim_handled():
    body = _read()
    assert " shim)" in body or "  shim)" in body, (
        "08-image-sign.sh missing 'shim' case (SDD-015 — operator MOK chain)"
    )


def test_secure_boot_enum_signed_handled():
    body = _read()
    assert " signed)" in body or "  signed)" in body, (
        "08-image-sign.sh missing 'signed' case (SDD-015 — operator PK direct)"
    )


def test_unknown_secure_boot_posture_fails():
    """SDD-015 verbatim: unknown posture MUST fail with operator-
    discoverable reason. Drift to silent-accept lets typoed YAML
    deploy unsigned images."""
    body = _read()
    has_unknown_fail = re.search(
        r"\*\).*\n.*unknown.*secure[_ ]boot",
        body, re.IGNORECASE | re.DOTALL
    )
    assert has_unknown_fail, (
        "08-image-sign.sh default case doesn't fail on unknown "
        "secure_boot value (SDD-015 — drift = typo deploys unsigned)"
    )


def test_unknown_posture_calls_state_step_fail():
    """Unknown posture MUST emit state_step_fail with kebab-case
    reason (operator state.yaml discovery surface)."""
    body = _read()
    assert "unknown-secure-boot" in body, (
        "08-image-sign.sh unknown-secure-boot fail reason missing "
        "(operator state.yaml discoverability)"
    )


# --- Operator-key mandate ("Operator-supplied keys NEVER in-repo") ---


def test_pk_key_env_var_referenced():
    """SDD-015 verbatim: SOVEREIGN_OS_PK_KEY (Platform Key, signed path).
    MUST be read from env — drift to hardcoded path = operator-key-
    mandate violation ('keys NEVER in-repo')."""
    body = _read()
    assert "SOVEREIGN_OS_PK_KEY" in body, (
        "08-image-sign.sh missing SOVEREIGN_OS_PK_KEY env var "
        "(operator mandate — keys via env, NEVER in-repo)"
    )


def test_pk_cert_env_var_referenced():
    body = _read()
    assert "SOVEREIGN_OS_PK_CERT" in body, (
        "08-image-sign.sh missing SOVEREIGN_OS_PK_CERT env var "
        "(operator mandate — keys via env, NEVER in-repo)"
    )


def test_mok_key_env_var_referenced():
    body = _read()
    assert "SOVEREIGN_OS_MOK_KEY" in body, (
        "08-image-sign.sh missing SOVEREIGN_OS_MOK_KEY env var "
        "(operator mandate — MOK chain via env)"
    )


def test_mok_cert_env_var_referenced():
    body = _read()
    assert "SOVEREIGN_OS_MOK_CERT" in body, (
        "08-image-sign.sh missing SOVEREIGN_OS_MOK_CERT env var "
        "(operator mandate — MOK chain via env)"
    )


def test_no_hardcoded_key_paths_in_repo():
    """OPERATOR MANDATE VERBATIM: 'Operator-supplied keys NEVER in-repo'.
    Script MUST NOT hardcode any *.key / *.crt / *.pem path. Drift
    here = operator-key-mandate violation = security exposure."""
    body = _read()
    # No hardcoded paths to keys/certs
    forbidden_patterns = [
        r"/etc/sovereign/[a-z]+\.key",
        r"/etc/sovereign/[a-z]+\.crt",
        r"keys/sovereign-pk\.key",
        r"keys/sovereign-pk\.pem",
        r"/opt/sovereign/.*\.key",
    ]
    for pat in forbidden_patterns:
        m = re.search(pat, body)
        assert not m, (
            f"08-image-sign.sh has hardcoded key/cert path matching "
            f"{pat!r}: {m.group() if m else ''} — VIOLATES operator "
            f"mandate 'Operator-supplied keys NEVER in-repo'"
        )


def test_shim_path_requires_mok_keys():
    """SDD-015: shim posture REQUIRES MOK keys. Without them, sbsign
    has nothing to sign with. Drift to silent-default = unsigned image
    despite shim posture."""
    body = _read()
    has_require = re.search(
        r"shim\)\s*\n.*SOVEREIGN_OS_MOK_KEY:\?",
        body, re.DOTALL
    )
    assert has_require, (
        "08-image-sign.sh shim path doesn't require SOVEREIGN_OS_MOK_KEY "
        "(SDD-015 — shim REQUIRES operator MOK chain)"
    )


def test_signed_path_falls_back_to_mok_with_warning():
    """SDD-015 verbatim: 'signed' posture falls back to MOK with a
    warning if PK env unset. Operator-discoverable warning preserves
    safety while not blocking dev iteration."""
    body = _read()
    has_fallback = (
        "PK env vars unset" in body
        or "falling back to MOK" in body.lower()
        or "fallback to MOK" in body.lower()
    )
    assert has_fallback, (
        "08-image-sign.sh signed path missing PK→MOK fallback warning "
        "(SDD-015 — fallback path with operator-discoverable warning)"
    )


# --- sbsign + sbverify safety contract ---


def test_uses_sbsign_for_signing():
    body = _read()
    assert "sbsign" in body, (
        "08-image-sign.sh missing sbsign (operator-named EFI signer; "
        "drift to a different signer breaks operator's signing chain)"
    )


def test_uses_sbverify_for_verification():
    """After sbsign, MUST sbverify — catches malformed signed binaries
    BEFORE the image ships. Drift losing verification silently ships
    broken signatures."""
    body = _read()
    assert "sbverify" in body, (
        "08-image-sign.sh missing sbverify post-sign verification "
        "(drift = ships broken signatures; operator boots fail silently)"
    )


def test_sbverify_failure_fails_step():
    """sbverify exit MUST propagate to state_step_fail. Drift to
    warn-and-continue lets unsigned/broken-sig images proceed to
    step 09 verify."""
    body = _read()
    has_fail = (
        "sbverify-failed" in body
        or ("sbverify" in body and "state_step_fail" in body)
    )
    assert has_fail, (
        "08-image-sign.sh sbverify failure doesn't trigger "
        "state_step_fail (drift = broken sig flows to step 09)"
    )


# --- Signing targets ---


def test_signs_vmlinuz_and_efi_binaries():
    """sbsign target patterns MUST include vmlinuz* + *.efi + bootx64.efi
    (the operator-named EFI boot chain artifacts)."""
    body = _read()
    has_vmlinuz = "vmlinuz" in body
    has_efi = "*.efi" in body or ".efi" in body
    assert has_vmlinuz, (
        "08-image-sign.sh missing vmlinuz* signing target "
        "(operator-named kernel EFI binary)"
    )
    assert has_efi, (
        "08-image-sign.sh missing .efi signing target "
        "(operator-named bootloader EFI binary)"
    )


# --- Dry-run + metrics observability ---


def test_dry_run_short_circuit():
    """SDD-016 + operator-verbatim CI safety: SOVEREIGN_OS_DRY_RUN
    MUST short-circuit BEFORE require_command sbsign (operator can
    dry-run on a build host without sbsign installed)."""
    body = _read()
    assert "SOVEREIGN_OS_DRY_RUN" in body, (
        "08-image-sign.sh missing SOVEREIGN_OS_DRY_RUN handling "
        "(operator-verbatim CI safety)"
    )


def test_metric_label_posture():
    """SDD-016 verbatim: signing metric MUST label by posture
    (operator-discovery: which posture is in use across builds)."""
    body = _read()
    has_posture_label = (
        'posture="' in body
        or 'posture=\\"' in body
    )
    assert has_posture_label, (
        "08-image-sign.sh missing posture=\"<...>\" metric label "
        "(SDD-016 verbatim — Grafana per-posture aggregation)"
    )


def test_legacy_disabled_alias_handled():
    """Operator-discoverable upgrade path: 'disabled' is the legacy
    alias from pre-SDD-015 profiles. MUST map to 'none' + warn so
    operator can update profile YAML."""
    body = _read()
    has_alias = (
        "disabled" in body
        and ("legacy" in body.lower() or "alias" in body.lower())
    )
    assert has_alias, (
        "08-image-sign.sh missing 'disabled' legacy alias handling "
        "(operator-discoverable upgrade path from pre-SDD-015 profiles)"
    )


def test_sdd_015_reference_in_comments():
    """Script header SHOULD cite SDD-015 + Q-006 (operator-discovery:
    a reader sees the binding to the SDD)."""
    body = _read()
    assert "SDD-015" in body and "Q-006" in body, (
        "08-image-sign.sh header missing SDD-015 + Q-006 reference "
        "(operator-discovery: the SDD-binding citation)"
    )
