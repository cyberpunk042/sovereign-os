# SDD-015 — Secure-boot posture (Q-006 resolution)

> Status: **review**
> Owner: cyberpunk042
> Last updated: 2026-05-16
> Closes findings: Q-006 (secure-boot posture)
> Derived from: SDD-003 (mkosi substrate), SDD-005 (initial profiles),
> `profiles/sain-01.yaml` § kernel.cmdline.secure_boot,
> `scripts/hooks/pre-install/preflight-tpm.sh`,
> `scripts/build/08-image-sign.sh`.

## Problem

Q-006 ("Secure-boot posture") has been open since PR 1. The profiles
already declare a value (`sain-01.kernel.cmdline.secure_boot: signed`,
`old-workstation: shim`, `minimal: signed`), but no SDD formalizes
what each value MEANS, what the build pipeline does for it, where
keys live, or what the operator-facing contract is. That's the gap
this SDD closes.

## Decision

**Three posture levels, declared per profile, with explicit semantics.**

| Posture value | Chain of trust | When to pick | What the build pipeline does |
|---|---|---|---|
| `none` | UEFI off / unsigned | dev VMs, throwaway test images | nothing — `step 08-image-sign` is a no-op |
| `shim` | Microsoft-signed shim → operator MOK key → kernel | constrained / legacy hardware where TPM2 may be absent or MOK enrollment via shim is the path of least friction (old-workstation) | sbsign vmlinuz with operator MOK; ship shim + MokManager in /boot/EFI |
| `signed` | direct sbsign with operator's PK (no shim) → kernel | production sovereign hardware (sain-01) — TPM2 present, operator owns Platform Key, no Microsoft-CA dep | sbsign vmlinuz + EFI binaries with operator's Platform Key; operator must enroll PK pre-install |

Posture is profile-declared (`kernel.cmdline.secure_boot`), validated
by `preflight-tpm.sh` (which SKIPs when posture != signed/shim), and
enforced by `08-image-sign.sh`.

## Key management

Keys live ONLY on the operator's machine. **Sovereign-os does NOT
ship signing keys** and never auto-generates keys with persistence
beyond a single build.

Operator-supplied env vars (used by `08-image-sign.sh`):

| Env var | Purpose | Default if unset |
|---|---|---|
| `SOVEREIGN_OS_MOK_KEY` | Path to operator's private MOK key | auto-generate ephemeral key + cert; operator must enroll the auto-generated cert post-build (workflow logged) |
| `SOVEREIGN_OS_MOK_CERT` | Path to operator's MOK certificate | (matches MOK_KEY) |
| `SOVEREIGN_OS_PK_KEY` | Platform Key — **preferred** for `posture: signed` | if PK_{KEY,CERT} are set, step 08 signs with the PK (the intended no-shim chain). If PK is unset but `SOVEREIGN_OS_MOK_{KEY,CERT}` are set, step 08 **falls back to the operator's MOK key with a warning** (still an operator-owned key; operator must enrol the MOK cert via `mokutil` post-install). Step 08 fails only if **neither** the PK nor the MOK key family is supplied. (Per the Round 31 hardening review; verified by `tests/nspawn/test_image_sign_gates.sh`: "signed + only MOK → falls back with warning", "signed + no key → fails".) |
| `SOVEREIGN_OS_PK_CERT` | Platform Key cert — preferred for `posture: signed` | (matches PK_KEY; see above) |

`preflight-tpm.sh` (added 2026-05-16) gates this at install-time:
- both `SOVEREIGN_OS_MOK_KEY` and `_CERT` set → both must be readable
- only one set → FAIL (incoherent state)
- neither set → log info (step 08 will auto-generate ephemeral)
- API key never logged (redacted in operator log)

## TPM2 binding

For posture=signed, the boot-time chain SHOULD measure into PCR-7
(secure-boot state) and PCR-11 (kernel + initrd). Disk encryption
(future SDD when ZFS native encryption decision lands) MAY bind to
PCR-7 to refuse mounting if secure-boot was disabled.

For posture=shim, PCR measurements happen but no auto-binding is
prescribed in this SDD.

For posture=none, no TPM operations occur.

## Build pipeline interaction

```
step 08-image-sign.sh:
  case profile.kernel.cmdline.secure_boot in
    none)    log_info "secure_boot=none — skipping sign step"; exit 0
    shim)    sbsign vmlinuz with MOK key + cert; copy shim/MokManager into ESP
    signed)  sbsign vmlinuz + EFI binaries with PK; refuse if PK env vars unset
```

The step is profile-conditioned but the gates live in the script —
no orchestrator-side conditional logic.

## Operator workflow per posture

### `posture: none`
- nothing to do.

### `posture: shim`
1. (one-time) generate MOK keypair:
   ```sh
   openssl req -newkey rsa:4096 -nodes -keyout MOK.priv -outform DER -keyout MOK.priv \
     -x509 -out MOK.der -days 3650 -subj "/CN=sovereign-os MOK $(date +%Y)/"
   ```
2. `SOVEREIGN_OS_MOK_KEY=/path/MOK.priv SOVEREIGN_OS_MOK_CERT=/path/MOK.der` for build.
3. After install, on first boot: enroll MOK via `mokutil --import MOK.der`,
   reboot, MokManager prompts for password, enroll, reboot.

### `posture: signed`
1. (one-time, more sensitive) generate Platform Key:
   ```sh
   openssl req -newkey rsa:4096 -nodes -keyout PK.priv -outform DER \
     -x509 -out PK.der -days 3650 -subj "/CN=sovereign-os PK $(date +%Y)/"
   sbsiglist --owner $(uuidgen) --type x509 --output PK.esl PK.der
   sbvarsign --key PK.priv --cert PK.der --output PK.auth PK PK.esl
   ```
2. Enroll PK via BIOS/UEFI setup (one-time, manual; firmware-specific).
3. `SOVEREIGN_OS_PK_KEY=/path/PK.priv SOVEREIGN_OS_PK_CERT=/path/PK.der` for build.
4. The image's vmlinuz + EFI binaries are sbsign'd; boot succeeds because
   firmware recognizes the operator's PK as trusted.

## Goals

1. **Posture per-profile** — sain-01 = signed (operator owns full chain);
   old-workstation = shim (constrained); minimal = signed (clean VM
   slate). Schema already enforces the enum.
2. **Keys never in-repo** — operator-supplied at build time; CI never
   has access to a real key (CI builds always run `posture: none` or
   `posture: shim` with ephemeral keys for smoke testing).
3. **Idempotent gate** — `preflight-tpm.sh` checks before commitments;
   `08-image-sign.sh` is the only step that signs; both refuse rather
   than fall through silently.
4. **TPM2 reachability checked pre-install** — preflight-tpm refuses
   when secure_boot is `signed`/`shim` but no TPM device node or no UEFI vars.
5. **API-key-safe logging** — env-var values never logged.

## Non-goals (this SDD)

- Does NOT prescribe key rotation cadence (operator-driven).
- Does NOT prescribe hardware-token-only keys (operator may use software
  files; YubiKey / TPM-resident keys are out of scope until specifically
  needed).
- Does NOT define LUKS / ZFS-native-encryption PCR binding (future SDD).
- Does NOT lock the MOK or PK certificate Common Name pattern beyond
  the operator's example above.

## Cross-references

- `profiles/sain-01.yaml` § kernel.cmdline.secure_boot=signed
- `profiles/old-workstation.yaml` § secure_boot=shim
- `profiles/minimal.yaml` § secure_boot=signed
- `schemas/profile.schema.yaml` § kernel.cmdline.secure_boot enum
- `scripts/hooks/pre-install/preflight-tpm.sh` (the runtime gate)
- `scripts/build/08-image-sign.sh` (the signing step)
- SDD-003 (substrate — mkosi supports SecureBoot=yes natively)
- SDD-005 (initial profiles where posture is declared)
- SDD-014 (decommission — destruction includes shredding any operator-
  derived keys cached during build)

## Open sub-questions (Q-015-X)

- **Q15-A** — Should sain-01 boot via shim instead of direct PK?
  Recommend: **direct PK** as currently declared — full sovereign chain,
  no Microsoft-CA dep. Operator can downgrade to shim if PK enrollment
  becomes blocking.
- **Q15-B** — Should we add a `posture: signed-with-tpm-binding` value
  that also configures clevis/systemd-cryptenroll to PCR-bind disk
  encryption keys? Recommend: **DEFER** until the ZFS native encryption
  decision lands (future SDD). Adding it now constrains that decision.
- **Q15-C** — Where do the operator's keys live between builds?
  Recommend: **operator's discretion** — sovereign-os doesn't mandate.
  Reasonable choices: GPG-encrypted in a personal vault; LUKS-encrypted
  external storage; hardware token. Doc the patterns in `docs/src/ops/`
  if operator wants guidance.
