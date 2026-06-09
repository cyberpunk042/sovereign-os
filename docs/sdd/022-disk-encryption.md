# SDD-022 — Disk encryption posture (Q15-B + ZFS-native-encryption)

> Status: **review**
> Owner: cyberpunk042
> Last updated: 2026-05-16
> Closes findings: SDD-015 Q15-B (TPM2 PCR-bound disk encryption)
> Derived from: SDD-015 (secure-boot), SDD-017 (ZFS layout), SDD-019
> (reproducibility), `scripts/hooks/during-install/zfs-pool-create.sh`,
> `preflight-tpm.sh`.

## Problem

SDD-015 Q15-B was tracked deferred: "Should we add a
`posture: signed-with-tpm-binding` value that also configures clevis/
systemd-cryptenroll to PCR-bind disk encryption keys? Recommend:
DEFER until the ZFS native encryption decision lands (future SDD).
Adding it now constrains that decision."

That future SDD is this one. The decision splits into two related
questions:

1. **Encryption mechanism** — LUKS (block layer, ext4-friendly) vs
   ZFS native encryption (dataset layer, ZFS-only) vs both?
2. **Key binding** — passphrase only · passphrase + TPM2 PCR · key
   in clear file · external (YubiKey / smartcard)?

## Decision

### Mechanism: **ZFS native encryption for zfs-tiered profiles; LUKS for ext4 profiles; encryption REQUIRED but key-policy operator-driven**

| Profile | layout | encryption mechanism | key-binding default | rationale |
|---|---|---|---|---|
| **sain-01** | zfs-tiered | ZFS native (aes-256-gcm) on `tank/context` and `tank/agents`; **NOT** on `tank/models` | passphrase + TPM2 PCR-7+11 | state-fabric must be encrypted; weights are reconstructible-from-HF so encryption adds CPU cost without sovereignty benefit |
| **headless** | ext4 | LUKS2 on root partition; LUKS2 on data raid1 | passphrase + TPM2 PCR-7+11 | server-class default per role-server posture |
| **developer** | ext4 | LUKS2 on root (optional — operator picks at install) | passphrase only | dev box; TPM-bind locks operator out of multi-boot workflows |
| **old-workstation** | ext4 | LUKS2 on root (optional) | passphrase only | constrained hardware; TPM may be absent |
| **minimal** | ext4 | none by default; LUKS2 if SOVEREIGN_OS_ENCRYPT=1 | passphrase only | VM baseline; operator decides per use case |

The `secure_boot` posture (SDD-015) is **orthogonal** to the
encryption posture. They compose:

| secure_boot | encryption | meaning |
|---|---|---|
| none | none | dev / throwaway |
| none | LUKS-pass | encrypted-at-rest but trust chain off |
| signed | none | trusted boot but data unencrypted (atypical) |
| signed | LUKS-pass | trusted boot + encryption, prompt every boot |
| signed | LUKS-pass-TPM | full chain: PCR-bound key auto-unlocks if PCRs match; tampered boot → operator falls back to passphrase |

### Key binding: TPM2 PCR-bound (sain-01 + headless) | passphrase only (others)

For sain-01 + headless, the install-time flow:

1. Operator provides a strong passphrase at install (SOVEREIGN_OS_ENCRYPT_PASSPHRASE env or interactive prompt).
2. `during-install/encryption-setup.sh` (lands in a future commit) configures:
   - LUKS2 root (ext4 profiles) OR `zfs create -o encryption=on -o keyformat=passphrase` (zfs-tiered)
   - systemd-cryptenroll (LUKS) OR a tpm2-tools-driven key file (ZFS) bound to PCR-7 (secure-boot state) + PCR-11 (kernel/initrd measurement)
3. First boot: if PCRs match → auto-unlock; else operator gets passphrase prompt (Plymouth's password callback per Round 33).

Recovery: operator's passphrase is the always-available unlock path.
TPM-bound key is convenience; passphrase is the floor.

### What's NOT bound

- `tank/models` (sain-01) — model weights, reconstructible-from-HF.
  Encrypting them costs decryption CPU on every model load with no
  sovereignty benefit (the same weights are publicly available).
- `/boot` and ESP — by design unencrypted (boot loader needs to read them);
  protected by secure-boot signature chain (SDD-015) instead.
- swap (when present) — operator-controlled separately; recommend
  `swapfile` (encrypted-zfs) or `cryptswap` for LUKS-encrypted random
  swap key per boot.

## Profile schema additions (forward-compat)

`schemas/profile.schema.yaml` will gain (in a follow-up commit):

```yaml
encryption:
  enabled: bool          # default: profile-dependent
  mechanism: enum [zfs-native, luks2, none]
  key_binding: enum [passphrase, passphrase-tpm-pcr, key-file]
  pcr_set: array of int  # default: [7, 11]
```

Until that lands, encryption is operator-driven via env vars at
install time:
- `SOVEREIGN_OS_ENCRYPT=1` — enable
- `SOVEREIGN_OS_ENCRYPT_PASSPHRASE_FILE=/path` — passphrase source
- `SOVEREIGN_OS_ENCRYPT_TPM_BIND=1` — enroll TPM PCR-bound unlock

## Preflight integration

`preflight-tpm.sh` (existing) already gates TPM2 readiness on the
`secure_boot` posture (runs for `signed`/`shim`, SDD-015 enum). SDD-022 adds a follow-up requirement: when
`SOVEREIGN_OS_ENCRYPT_TPM_BIND=1`, preflight-tpm SHOULD verify:
- /dev/tpm0 + tpm2_pcrread sha256 banks accessible
- /sys/firmware/efi/efivars present (EFI vars writable for binding)
- tpm2-tools `tpm2_createprimary` smoke-test succeeds

(Implementation lands in a follow-up commit; SDD locks the contract.)

## Operational workflow

```sh
# Install with encryption + TPM binding (sain-01 example)
SOVEREIGN_OS_PROFILE=sain-01 \
SOVEREIGN_OS_ENCRYPT=1 \
SOVEREIGN_OS_ENCRYPT_TPM_BIND=1 \
SOVEREIGN_OS_ENCRYPT_PASSPHRASE_FILE=/run/install/passphrase \
  sudo scripts/build/orchestrate.sh run

# Install without encryption (dev profile)
SOVEREIGN_OS_PROFILE=developer \
  sudo scripts/build/orchestrate.sh run
```

Recovery (if TPM-bound unlock fails post-update):
```sh
# operator interactively enters the passphrase at Plymouth prompt
# Then re-enroll PCRs against the new measurements:
sudo sovereign-osctl encryption reseal-tpm
```

## Layer 3 coverage (current + planned)

Current: `preflight-tpm.sh` is gated by `test_orchestrator_preflight.sh`
(profile-conditioned: runs for secure_boot `signed`/`shim`, SKIPs for `none`/unset).

Planned (Stage 2+ follow-up commits):
- `tests/nspawn/test_encryption_gates.sh` — encryption-setup.sh gates
  (operator-explicit `SOVEREIGN_OS_ENCRYPT` required; refuses without
  passphrase source; idempotent re-run)
- Layer 4 (QEMU): boot an encrypted-LUKS image, verify passphrase
  unlock works, verify a tampered-PCR boot falls back to passphrase
  (not auto-unlock)

## Goals

1. **State-fabric at-rest encrypted by default for production
   profiles** — sain-01 + headless. operator opt-out via env, not
   opt-in.
2. **Passphrase is always the floor** — TPM convenience never replaces
   passphrase recovery path.
3. **Encryption posture is orthogonal to secure-boot posture** —
   operators pick both axes independently.
4. **Schema additions are forward-compatible** — current operator
   workflow via env vars works until the schema lands.
5. **Reconstructible data not encrypted** — model weights (HF-pullable)
   stay unencrypted; CPU cost not justified.

## Non-goals (this SDD)

- Does NOT pick a specific TPM2-tools command sequence (operator-side
  detail; tpm2_createpolicy + tpm2_loadexternal patterns documented at
  `man tpm2-tools(1)`).
- Does NOT prescribe key escrow / fleet recovery semantics (single-
  operator boxes for now; fleet-mode key management is Stage 4 <!-- anti-min-waiver: R480 fleet-mode-key-management-anchored-to-Stage-4-reliability-per-CLAUDE-md-scale-axis -->
  reliability per CLAUDE.md scale axis).
- Does NOT add YubiKey/smartcard backing — operator can extend via
  systemd-cryptenroll's pkcs11 support without sovereign-os changes.

## Open sub-questions (Q22-X)

- **Q22-A** — Should `tank/agents` be encrypted by default on sain-01?
  Recommend: **YES** — sub-agent scratch can carry secrets in transit.
  Cheap to encrypt (zstd-3 already; aes-256-gcm has hardware accel).
- **Q22-B** — Plymouth password callback ergonomics: bullet-feedback
  vs masked-input? Recommend: **bullet-feedback** (already wired in
  Round 33's sovereign.script).
- **Q22-C** — Should we add a `posture=signed-with-tpm-binding` value
  to the kernel.cmdline.secure_boot enum to combine SDD-015 + SDD-022
  in one field? Recommend: **NO** — keep axes orthogonal; combination
  is the cross-product of the two enums.

## Cross-references

- SDD-015 § Q15-B (the deferred item this SDD closes)
- SDD-017 (ZFS layout — encryption is per-dataset)
- SDD-019 (reproducibility — image-encrypted-at-rest is independent
  from build-time reproducibility)
- `scripts/hooks/pre-install/preflight-tpm.sh`
- `scripts/hooks/during-install/zfs-pool-create.sh` (will gain
  encryption=on for sain-01 in follow-up commit)
- `whitelabel/default/overlays/plymouth-theme/sovereign.script` § password callback (Round 33)
