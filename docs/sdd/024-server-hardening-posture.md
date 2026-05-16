# SDD-024 — role-server + role-workstation hardening posture (Rounds 96-104 codification)

> Status: **review**
> Owner: cyberpunk042
> Last updated: 2026-05-16
> Derived from: `profiles/mixins/role-server.yaml` +
> `profiles/mixins/role-workstation.yaml`, decisions D-016 (Round 96
> server hardening drop-ins; Round 98 SSH addition; Round 101 pwquality;
> Round 102 DEST_PREFIX) + D-017 (Round 104 workstation hardening),
> operator verbatim "we always deliver IaC" + "Reach our ultimate
> sovereignty".

## Problem

The `role-server` mixin installed auditd, fail2ban, unattended-upgrades,
chrony, and openssh-server as packages — and that's where the
hardening ended. Stock Debian defaults:

- auditd: empty ruleset (auditctl shows zero rules), captures nothing
  operator-actionable
- fail2ban: no jails enabled by default
- unattended-upgrades: not configured to run anything
- sshd: PasswordAuthentication yes, PermitRootLogin without-password,
  permissive cipher suite including AES-CBC and SHA-1 MACs

A `headless` profile booted onto bare-metal would advertise "hardened
server" but deliver mass-deployment defaults. That is not what
"we always deliver IaC" (operator verbatim, sacrosanct) means.

## Decision

Ship four opinionated hardening drop-ins as IaC under `config/server/`,
applied at first-boot by a profile-aware hook on the role-server
mixin chain. Each drop-in has load-bearing invariants pinned at
Layer 1 lint; silent weakening fails CI.

### Drop-in inventory

| Source | Destination | Invariants pinned in lint |
|---|---|---|
| `config/server/auditd.rules` | `/etc/audit/rules.d/sovereign-os.rules` | `-e 2` immutable · `-f 2` panic-on-loss · watches on sudoers/passwd/shadow/sshd_config/sovereign-os/tetragon · privileged syscalls (init_module/delete_module/settimeofday) |
| `config/server/fail2ban-jail.local` | `/etc/fail2ban/jail.d/sovereign-os.local` | `nftables` backend (not iptables) · `systemd` log backend · `[sshd]` enabled aggressive · `[recidive]` enabled (1w ban on 3rd offense) |
| `config/server/unattended-upgrades.conf` | `/etc/apt/apt.conf.d/52sovereign-os-unattended.conf` | ONLY `Debian-Security` origin auto-applied · main-channel commented out · `Automatic-Reboot="false"` |
| `config/server/sshd.conf` | `/etc/ssh/sshd_config.d/50sovereign-os.conf` | `PermitRootLogin no` · `PasswordAuthentication no` · `AuthenticationMethods publickey` · all forwarding `no` · no SHA-1 in any algorithm directive · no `-cbc` ciphers |

### Hook contract

`scripts/hooks/post-install/apply-server-hardening.sh`:

- Profile-aware: detects `role-server` membership via the YAML `mixins`
  list. Other profiles SKIP cleanly with explanatory log + Layer B
  `result="skipped"` counter.
- Idempotent: reports `applied / unchanged / failed` counts. Re-running
  on already-hardened state is a no-op. Drift detection: modified
  drop-in is re-applied; unmodified drop-ins skipped.
- DRY-RUN-safe: `SOVEREIGN_OS_DRY_RUN=1` lists the actions without
  side effects.
- **DEST_PREFIX-aware**: `SOVEREIGN_OS_HARDENING_DEST_PREFIX=<path>`
  redirects all destinations under that root. Used for chroot /
  container / image-build-tree workflows. Service reload is SKIPPED
  in this mode (we're not on the running system).
- Best-effort service reload: in chroot / container where systemctl
  is unwired, warns instead of failing.
- SSH safety gate: `sshd -t` config validation runs BEFORE `systemctl
  reload ssh` — never reload a syntactically-broken config that would
  lock the operator out of their own machine.
- Layer B emission: `sovereign_os_post_install_server_hardening_total{profile,result}`
  + `sovereign_os_post_install_server_hardening_applied{profile}` gauge.

### Operator override surface

Each drop-in uses a deliberately-low numeric prefix or the standard
`*.d/*.conf` / `*.local` convention. Operators override per-host by
dropping a lexicographically-LATER file:

| sovereign-os drop-in | Operator override file |
|---|---|
| `/etc/audit/rules.d/sovereign-os.rules` | `/etc/audit/rules.d/zz-operator.rules` |
| `/etc/fail2ban/jail.d/sovereign-os.local` | `/etc/fail2ban/jail.d/zz-operator.local` |
| `/etc/apt/apt.conf.d/52sovereign-os-unattended.conf` | `/etc/apt/apt.conf.d/99operator-unattended.conf` |
| `/etc/ssh/sshd_config.d/50sovereign-os.conf` | `/etc/ssh/sshd_config.d/99operator.conf` |

DEACTIVATE entirely by removing the sovereign-os file (audit) or by
the operator file overriding all keys (fail2ban / sshd / unattended).

### Sovereignty posture

- "we always deliver IaC" (operator verbatim, sacrosanct) — the
  hardening is content, not advertising.
- "Reach our ultimate sovereignty" — operators can audit + override
  every line; no opaque tooling between operator and sshd_config.
- "honesty over cheats and lies" — the advertised role-server posture
  now matches runtime reality byte-for-byte.

## Profile applicability (Round 104 update — both axes)

| Profile | Mixin | Hardening hook | Drop-ins applied |
|---|---|---|---|
| **headless** | role-server | apply-server-hardening | 5 (auditd · fail2ban · unattended · sshd-server · pwquality) |
| **sain-01** | role-workstation | apply-workstation-hardening | 4 (auditd · unattended · sshd-workstation · pwquality) — no fail2ban (Tetragon perimeter handles IDS in-kernel) |
| **old-workstation** | role-workstation | apply-workstation-hardening | 4 (same 4 as sain-01) |
| **developer** | role-developer | — | none (operator dev box; restrictive auditd/ssh would impede workflow) |
| **minimal** | role-headless | — | none (VM baseline; operator picks their own posture) |

Future role-server-composing profiles (e.g. `headless-edge`,
`headless-zfs-tiered`) inherit server hardening automatically.
Future role-workstation-composing profiles inherit workstation hardening
automatically.

## role-workstation deltas vs role-server (Round 104)

Workstation hardening reuses the 3 universal drop-ins from
`config/server/` (auditd, pwquality, unattended-upgrades) and adds
`config/workstation/sshd.conf` with deliberate deviations:

| Directive | server posture | workstation posture | rationale |
|---|---|---|---|
| `PasswordAuthentication` | no | **yes** | console-fallback when operator forgets pubkey |
| `AuthenticationMethods` | publickey | publickey password | either works alone |
| `AllowAgentForwarding` | no | **yes** | dev hop pattern is standard workstation flow |
| `AllowTcpForwarding` | no | **yes** | dev hop pattern |
| fail2ban | enabled | **omitted** | workstation not internet-facing; sain-01 has Tetragon |

Everything else (no root login · no SHA-1 · no `-cbc` ciphers · modern
KEX/MACs · session timeouts) MIRRORS server posture — those are
universal hardening, not server-specific.

## Test gates

| Layer | Gate | Asserts |
|---|---|---|
| L1 | `tests/lint/test_server_hardening_config.py` | 10 invariant suites (dir present · auditd locked · fail2ban locked · unattended security-only · server-sshd hardened · pwquality minlen/4-classes/enforce-root · hook executable · headless registers hook · **workstation-sshd looser-but-still-hardened** · **sain-01 + old-workstation register workstation hook**) |
| L3 | `tests/nspawn/test_apply_workstation_hardening.sh` | 13 assertions (SKIP non-workstation · DRY-RUN sain-01 + old-workstation · 4-not-5 drop-in count · workstation sshd content correct · fail2ban deliberately ABSENT · live apply · idempotency · Layer B) |
| L3 | `tests/nspawn/test_apply_server_hardening.sh` | 25 assertions (SKIP minimal · DRY-RUN headless · source readable · invariants verified at source · metric emission · **live apply via DEST_PREFIX** · all 5 files land · mode 0644 · byte-identical to source · idempotent re-run · drift detection · reload-skipped-in-prefix-mode · success counter) |
| L1 | `tests/lint/test_hook_layer_b_coverage.py` | `apply-server-hardening.sh` participates in Layer B emission |
| L1 | `tests/lint/test_metric_inventory_lockstep.py` | Two new metrics documented in inventory |

## Open sub-questions (Q24-X tracked)

- **Q24-A** — Should auditd ship a per-profile rule overlay
  (e.g. `auditd.headless.rules` vs `auditd.sain-01.rules`)? Recommend:
  NO at foundation — single ruleset keeps the audit surface uniform
  across sovereign-os fleet. Reconsider at Stage 4+ if per-profile
  forensic needs diverge.
- **Q24-B** — Should fail2ban's `[recidive]` ban escalate further on
  4th offense (1w → 1m)? Recommend: NO — operators can extend via
  `zz-operator.local`. Sovereign-os ships sane-default escalation,
  not aggressive-default escalation.
- **Q24-C** — Should `apply-server-hardening.sh` also configure
  `/etc/issue.net` (network banner shown before login) symmetrically
  with `/etc/issue` (post-login)? Recommend: YES at Stage 3+ when the
  whitelabel renderer learns the issue.net surface (currently only
  /etc/issue is rendered).
- **Q24-D** — Should the hook generate a `/etc/security/pwquality.conf`
  drop-in for headless's pubkey-only fleet (operators with sudo still
  use passwords)? **RESOLVED (Round 101)** — YES; shipped as
  `config/server/pwquality.conf` (5th drop-in). minlen 14 + all four
  character classes required + enforce_for_root + maxsequence/repeat
  limits. CIS Debian 12 § 5.4.1 minimum honored.

## Cross-references

- `profiles/mixins/role-server.yaml` — package layer; this SDD is the
  config layer
- `profiles/headless.yaml` § hooks.post_install_first_boot — hook
  registration
- `config/server/{auditd.rules, fail2ban-jail.local,
  unattended-upgrades.conf, sshd.conf, README.md}` — the IaC itself
- `scripts/hooks/post-install/apply-server-hardening.sh` — the
  applier
- `tests/lint/test_server_hardening_config.py` — invariant gate
- `tests/nspawn/test_apply_server_hardening.sh` — hook gate
- Decision **D-016** (Round 96 hardening drop-ins; Round 98 SSH
  addition; Round 99 operator README)
- SDD-016 (observability bindings) — Layer B counters emitted by hook
- SDD-023 (alerts contract) — sovereignty posture echoed here
- Operator verbatim (sacrosanct):
  "we always deliver IaC",
  "Reach our ultimate sovereignty",
  "honesty over cheats and lies"
