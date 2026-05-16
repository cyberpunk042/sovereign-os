# Profile: headless — bare-metal server

> Bare-metal headless server. Audit + intrusion-prevention + automatic
> security updates + chrony + hardened SSH out-of-the-box. No GUI, no
> AI stack, no VFIO.
>
> Profile YAML: [`profiles/headless.yaml`](../../../profiles/headless.yaml).

---

## Hardware target

| Component | Expected |
|---|---|
| CPU | x86-64-v3 server-class (8c/16t minimum) |
| GPU | none |
| RAM | 16 GB minimum, 32 GB+ recommended (ECC preferred) |
| Storage | NVMe rootfs + dual SATA/SAS SSD in raid1 for data |
| Network | 1 GbE LAN at minimum |
| Secure boot | `signed` (operator-owned PK chain — server-class default) |

---

## What's profile-specific

| Aspect | headless | Differs from |
|---|---|---|
| Kernel | substrate-default | sain-01 uses custom |
| Storage | ext4 rootfs + raid1 data | sain-01 uses zfs-tiered |
| GUI | none | (matches minimal/developer) |
| Networking | systemd-networkd; no NetworkManager | minimal uses cloud-init |
| Mixins | **role-server** + whitelabel-default + observability-tier-1 | role-workstation for sain-01, role-developer for developer |
| Hardening | 5 IaC drop-ins: auditd · fail2ban · unattended-upgrades · sshd-server · pwquality | sain-01 has 4 workstation drop-ins (no fail2ban — workstation isn't internet-facing) |
| SSH | pubkey-only, no password, no agent/tcp/x11 forwarding, no SHA-1, no -cbc | sain-01 has looser SSH (workstation patterns) |
| First-login assistant | NOT registered (server boots to ready state; operator drives via ssh + sovereign-osctl) | sain-01 has it as opt-in |
| Inference router | none active | sain-01 has all 4 tiers |

---

## Build

```sh
# Dry-run
SOVEREIGN_OS_PROFILE=headless scripts/build/orchestrate.sh run --dry-run

# Real build (server-class default = signed posture; needs operator-owned keys)
SOVEREIGN_OS_PROFILE=headless \
SOVEREIGN_OS_DB_KEY=/path/db.key \
SOVEREIGN_OS_DB_CERT=/path/db.crt \
SOVEREIGN_OS_PK_KEY=/path/PK.key \
SOVEREIGN_OS_PK_CERT=/path/PK.crt \
  sudo scripts/build/orchestrate.sh run

# Verify
sovereign-osctl audit provenance --deep build/headless/output/build-provenance.json
```

---

## Install + boot

```sh
sovereign-osctl install image --plan build/headless/output/headless.raw --to /dev/nvme0n1
SOVEREIGN_OS_CONFIRM_DESTROY=YES \
  sudo sovereign-osctl install image build/headless/output/headless.raw --to /dev/nvme0n1
```

First-boot hook order:
1. `friction-audit-runtime` — minimal checks (no GPU/VFIO/Tetragon)
2. `apply-server-hardening` — applies all 5 IaC drop-ins (auditd · fail2ban · unattended-upgrades · sshd-server · pwquality)
3. (no first-login-assistant; server reaches ssh-ready state quietly)

After boot, ssh in via pubkey (the only auth method configured by default).

---

## Daily use

```sh
sovereign-osctl profiles switch headless
sovereign-osctl status
sovereign-osctl doctor                       # checks chrony + auditd + fail2ban + sshd config
sovereign-osctl audit drift                  # crucial for servers — has hardening drifted?
sovereign-osctl alerts                       # rule-derived (security updates pending? perimeter? recurrent hooks running?)
sovereign-osctl maintenance security-check   # apt security updates count
sovereign-osctl maintenance log-rotate       # rotate journald + JSONL logs
sovereign-osctl perimeter status             # if Tetragon is enabled (opt-in for headless)
```

Recurrent timers (active by default on headless):
- `sovereign-security-update-check.timer` (daily)
- `sovereign-log-rotate.timer` (daily)
- `sovereign-backup-snapshot.timer` (daily, if ZFS available)
- `sovereign-alerts-check.timer` (hourly)

---

## What this profile is FOR

1. **Bare-metal servers** — fleet members, edge nodes, build hosts.
2. **Sovereignty for non-AI workloads** — same operator quality bar applies to non-AI infra: signed kernel, hardened sshd, auditd, perimeter.
3. **Auditable production deployments** — every hardening drop-in is in `config/server/` with L1 lint pinning load-bearing invariants. Audit drift detection on demand.

## What this profile is NOT FOR

- Workstations (use developer or sain-01)
- AI inference (use sain-01)
- VMs you don't care about (use minimal)

---

## Customization

| Want to… | How |
|---|---|
| Loosen sshd | drop a `99operator.conf` in `/etc/ssh/sshd_config.d/` (lexicographically wins) |
| Enable Tetragon | `sovereign-osctl hooks add post_install_first_boot scripts/hooks/post-install/tetragon-policy-load.sh --profile headless` |
| Change fail2ban policy | drop a `99operator.local` in `/etc/fail2ban/jail.d/` |
| Disable unattended-upgrades | edit `profiles/headless.yaml § hooks.post_install_first_boot` to remove apply-server-hardening (or drop a `99operator-unattended.conf` in `/etc/apt/apt.conf.d/`) |
| Add a fleet-management role | `sovereign-osctl profiles fork headless my-fleet-host` |

---

## Hardening invariants (pinned in CI)

The 5 drop-ins under `config/server/` have load-bearing invariants
enforced by `tests/lint/test_server_hardening_config.py`. Silent
weakening fails CI. See [`config/server/README.md`](../../../config/server/README.md)
for the full invariant list + override recipes.
