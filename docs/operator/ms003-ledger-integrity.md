# MS003 ledger-integrity runbook

Operator runbook for the MS003 mutation-record signing chain's **verifier
half** (F-2026-034). The producer half signs every durable decision/mutation
record with the operator ed25519 key (`scripts/lib/ms003.py sign()`); the
verifier half — the daily `sovereign-ms003-verify.timer` sweep + the
`sovereign-osctl ms003 verify` on-demand verb — checks those records against
the operator **trust-anchor store** and emits the
`sovereign_os_ms003_*` metrics these alerts fire on.

Standing rule: we do not minimize anything. This surface is pure observability
(R10212) — verification never mutates a ledger.

## Provisioning (once per operator)

```sh
sovereign-osctl ms003 gen-key            # mint the operator ed25519 key
sovereign-osctl ms003 anchor-add --from-key   # trust this node's own key locally
sovereign-osctl ms003 pubkey             # export the anchor to share with selfdef
```

Verify on demand at any time:

```sh
sovereign-osctl ms003 verify             # sweep /var/lib/sovereign-os
sovereign-osctl ms003 verify --strict /var/lib/sovereign-os/memory
```

Exit codes: `0` clean · `2` tamper / unknown signer · `3` (`--strict`) unsigned
records present.

## MS003LedgerTamper (critical)

A durable record failed ed25519 verification, or was signed by a key that is
**not** in the trust-anchor store (`/etc/sovereign-os/ms003-trust-anchors/`).

Diagnose:

```sh
sovereign-osctl ms003 verify /var/lib/sovereign-os        # see per-status counts
sovereign-osctl ms003 anchor-list                         # is the expected keyid trusted?
grep MS003_INTEGRITY /mnt/vault/context/security_audit.log # forensic record
```

- **`invalid-signature`** — the record's bytes no longer match its signature:
  the payload was altered after signing, or the ledger is corrupt. Treat as a
  tamper event; preserve the ledger file for forensics before any repair.
- **`unknown-keyid`** — the record is validly signed but by a key you have not
  trusted. If it is a legitimate operator key (e.g. after a key rotation),
  install it with `sovereign-osctl ms003 anchor-add <pubkey-b64url>`; otherwise
  it is an unexpected signer — investigate.

## MS003LedgerUnhealthy (warning)

`sovereign_os_ms003_ledger_status` is 0 without an outright tamper. The common
cause: `sovereign_os_ms003_key_loaded=1` (an operator key IS provisioned) but
`sovereign_os_ms003_records{status="unsigned-placeholder"}` is non-zero — records
that predate key provisioning, or that hit a signing failure, still carry the
`unsigned-pending-MS003` placeholder.

```sh
sovereign-osctl ms003 status              # confirm signing is ACTIVE
sovereign-osctl ms003 verify /var/lib/sovereign-os
```

New records written after provisioning sign automatically; pre-key history stays
unsigned by design (it is not rewritten). If the count is only historical, this
is informational; if it grows, signing is failing — check `openssl` availability
and the key path (`$SOVEREIGN_OS_MS003_KEY`).

## MS003VerifierOverdue (warning)

`time() - sovereign_os_ms003_verify_last_run_timestamp` exceeded 36h — the daily
sweep has not reported.

```sh
systemctl status sovereign-ms003-verify.timer sovereign-ms003-verify.service
journalctl -u sovereign-ms003-verify.service -b
systemctl start sovereign-ms003-verify.service   # run one now
```

Common causes: the timer was disabled, the host was down at the 04:30 fire time
(the timer is `Persistent=true`, so it catches up on next boot), or the sweep
errored. The integrity signal is only as fresh as the last run.
