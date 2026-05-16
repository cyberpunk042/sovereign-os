# sovereign-os workstation-hardening drop-ins (role-workstation profiles)

Per SDD-024 + decision **D-017** (Round 104). Workstation-side IaC
for the hardening posture promised by the `role-workstation` mixin
(consumed by `profiles/sain-01.yaml` + `profiles/old-workstation.yaml`).

## What lives here

| File | Destination | Why workstation-specific |
|---|---|---|
| `sshd.conf` | `/etc/ssh/sshd_config.d/50sovereign-os.conf` | Allows password auth fallback + agent/tcp forwarding (dev hop pattern); server posture is pubkey-only with no forwarding |

The other 3 drop-ins (auditd / pwquality / unattended-upgrades) are
**shared with role-server** and live under `config/server/`. The
workstation hook copies all four into place.

Deployment hook:
`scripts/hooks/post-install/apply-workstation-hardening.sh`. Runs at
first-boot on profiles whose mixin chain composes `role-workstation`.
SKIPs cleanly on other profiles. Idempotent. DEST_PREFIX-aware for
chroot / container / image-build target trees (service reload is
skipped in that mode).

## role-workstation vs role-server (intentional deltas)

| Aspect | Server (headless) | Workstation (sain-01, old-workstation) |
|---|---|---|
| Password auth | NO (pubkey-only) | YES (console fallback) |
| AuthenticationMethods | `publickey` | `publickey password` (either works) |
| Agent forwarding | NO | YES (standard dev hop pattern) |
| TCP forwarding | NO | YES |
| fail2ban | enabled | OMITTED (workstation not internet-facing; sain-01 uses Tetragon for in-kernel IDS) |
| auditd | identical | identical (universal hardening) |
| pwquality | identical | identical (sudo/su/passwd still need passwords) |
| unattended-upgrades | identical | identical (Security-only, no auto-reboot) |

Universal hardening (no root login · no SHA-1 · no `-cbc` ciphers ·
modern KEX/MACs · session timeouts · Banner /etc/issue) MIRRORS server
posture — those are not server-specific.

## Operator override

Same pattern as server hardening: drop a lexicographically-later file:

```
/etc/audit/rules.d/zz-operator.rules
/etc/apt/apt.conf.d/99operator-unattended.conf
/etc/ssh/sshd_config.d/99operator.conf
/etc/security/pwquality.conf.d/99operator.conf
```

Common workstation override examples:

```sh
# Disable password auth on a workstation that's NOT console-attached
# (e.g., headless dev VM)
echo "PasswordAuthentication no" | sudo tee /etc/ssh/sshd_config.d/99operator.conf
```

```sh
# Allow X11 forwarding for one specific Match user
sudo tee /etc/ssh/sshd_config.d/99operator-x11.conf <<'EOF'
Match User dev-trusted
    X11Forwarding yes
EOF
```

## Testing

```sh
# Workstation invariants (suite within the shared lint test)
python3 -m pytest tests/lint/test_server_hardening_config.py::test_workstation_sshd_present_and_looser_than_server -v

# Hook gate (DRY-RUN + live-apply via DEST_PREFIX)
tests/nspawn/test_apply_workstation_hardening.sh   # 13 assertions

# Manual re-run on a live system
sudo SOVEREIGN_OS_PROFILE=sain-01 \
  /opt/sovereign-os/scripts/hooks/post-install/apply-workstation-hardening.sh

# Apply into a target tree (chroot / container / image build):
SOVEREIGN_OS_PROFILE=sain-01 \
SOVEREIGN_OS_HARDENING_DEST_PREFIX=/mnt/target \
  /opt/sovereign-os/scripts/hooks/post-install/apply-workstation-hardening.sh
```

## Cross-references

- SDD-024 § role-workstation deltas vs role-server
- Decision **D-017** — Round 104 workstation hardening parallel
- `config/server/README.md` — server-side companion
- `profiles/sain-01.yaml` + `profiles/old-workstation.yaml` —
  hook registration
- `scripts/hooks/post-install/apply-workstation-hardening.sh` — the
  applier (parallel to apply-server-hardening; shares 3 of 4 sources
  with `config/server/`)
- `tests/lint/test_server_hardening_config.py` —
  `test_workstation_sshd_present_and_looser_than_server` +
  `test_workstation_profiles_register_hook`
- `tests/nspawn/test_apply_workstation_hardening.sh` — 13 assertions
