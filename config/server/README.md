# sovereign-os server-hardening drop-ins (role-server profiles)

Per SDD-016 + decision **D-016** (Round 96) + Round 98 SSH addition.
Operator-facing IaC for the hardening posture promised by the
`role-server` mixin (currently composed by `profiles/headless.yaml`).

## What lives here

| File | Destination | Reload command |
|---|---|---|
| `auditd.rules` | `/etc/audit/rules.d/sovereign-os.rules` | `augenrules --load` or `systemctl restart auditd` |
| `fail2ban-jail.local` | `/etc/fail2ban/jail.d/sovereign-os.local` | `systemctl reload fail2ban` |
| `unattended-upgrades.conf` | `/etc/apt/apt.conf.d/52sovereign-os-unattended.conf` | none (timer-driven) |
| `sshd.conf` | `/etc/ssh/sshd_config.d/50sovereign-os.conf` | `sshd -t && systemctl reload ssh` |

Deployment hook: `scripts/hooks/post-install/apply-server-hardening.sh`.
Runs at first-boot on profiles whose mixin chain composes `role-server`.
SKIPs cleanly on other profiles. Idempotent — re-running reports
`applied / unchanged / failed` counts.

## Load-bearing invariants (pinned in CI)

Layer 1 lint `tests/lint/test_server_hardening_config.py` pins
the invariants below. Silent weakening fails CI. Deliberate relaxation
requires an explicit `# HARDENING-WAIVER: <reason>` comment in the
file.

### auditd.rules
- `-e 2` — ruleset immutable until reboot (defeats runtime tampering by attacker-with-root)
- `-f 2` — panic on audit-loss (silent loss is worse than denial of service)
- Watches: sudoers · passwd · shadow · sshd_config · /etc/sovereign-os/ · /var/lib/sovereign-os/ · /etc/tetragon/
- Syscalls: init_module · delete_module · settimeofday · adjtimex · clock_settime

### fail2ban-jail.local
- `nftables` backend (NOT iptables — sovereign-os ships nftables-only)
- `systemd` log backend (no fail2ban-specific log file parsing)
- `[sshd]` enabled with aggressive mode + maxretry 3
- `[recidive]` enabled with 1-week ban on 3rd offense in a day

### unattended-upgrades.conf
- ONLY `Debian-Security` origin auto-applied
- Main-channel updates COMMENTED — operator opt-in only
- `Automatic-Reboot="false"` — operator owns reboot windows

### sshd.conf
- `PermitRootLogin no` + `PasswordAuthentication no` + `PermitEmptyPasswords no`
- `AuthenticationMethods publickey` (pubkey-only; no GSSAPI, no host-based)
- Forwarding: X11 / Agent / TCP / Tunnel ALL no by default
- No SHA-1 in KexAlgorithms / MACs / HostKey / PubkeyAccepted
- No `-cbc` ciphers (only AEAD: GCM + chacha20-poly1305 + CTR)
- `Banner /etc/issue` — whitelabel motd surfaced at SSH login

## Operator overrides

Each drop-in deliberately uses a low number prefix (`50`, `52`) or
the standard `*.local` / `*.d/*.conf` extension pattern. Operators
override per-host by dropping a lexicographically-LATER file:

```
/etc/audit/rules.d/zz-operator.rules
/etc/fail2ban/jail.d/zz-operator.local
/etc/apt/apt.conf.d/99operator-unattended.conf
/etc/ssh/sshd_config.d/99operator.conf
```

The later file wins. To DEACTIVATE a sovereign-os drop-in entirely:

```sh
# auditd — remove sovereign-os rules, augenrules picks up the change
sudo rm /etc/audit/rules.d/sovereign-os.rules && sudo augenrules --load

# fail2ban — disable individual jail by overriding [jail-name] enabled=false
# in zz-operator.local

# unattended-upgrades — operator's 99* file overrides the 52* file

# sshd — operator's 99* file overrides the 50* file
```

## Testing

```sh
# All hardening invariants enforced at lint time
python3 -m pytest tests/lint/test_server_hardening_config.py -v

# Hook behavior under DRY-RUN (no root needed)
tests/nspawn/test_apply_server_hardening.sh

# On a live install, the hook runs at first-boot. Manually re-run with:
sudo SOVEREIGN_OS_PROFILE=headless \
  /opt/sovereign-os/scripts/hooks/post-install/apply-server-hardening.sh
```

## Cross-references

- SDD-016 § Layer A audit (auditd surfaces what Layer A misses)
- SDD-023 § sovereignty posture (operator-derived alerts close the loop)
- Decision **D-016** — Headless server hardening: actual IaC drop-ins
- `profiles/mixins/role-server.yaml` — which profiles consume this
- `tests/lint/test_server_hardening_config.py` — invariant gate
- `tests/nspawn/test_apply_server_hardening.sh` — hook gate
