# Operator env files & secrets — the `/etc/sovereign-os/*.env` convention

> Canonical answer to the operator's 2026-07-19 question (verbatim): *"so
> this require a .env. where does go this .env ? or is it somthing else ?"*
> — it is **something else**: there is **no repo `.env`** anywhere in
> sovereign-os. This page is the doctrine + the empirical inventory
> (verified 2026-07-19 by grepping every `EnvironmentFile=` in
> `systemd/system/`).

## The doctrine (three rules)

1. **Configs carry env-var NAMES, never values.** A TOML config that needs
   a secret writes `api_key = "env:RESEND_API_KEY"` — the consumer resolves
   the variable at delivery time. Tokens/URLs/keys never live in-repo and
   never in `/etc/sovereign-os/*.toml`.
2. **Values live in operator-owned env files at `/etc/sovereign-os/*.env`**
   — `0600`, root-owned, one file per concern. systemd units load them with
   `EnvironmentFile=-/etc/sovereign-os/<name>.env`; the leading `-` means a
   missing file is tolerated (the dependent feature stays off instead of
   crashing the unit).
3. **Interactive CLI use sources the same file** — no second copy:

   ```sh
   set -a; . /etc/sovereign-os/notify.env; set +a
   sovereign-osctl notifykit test --priority high --urgency high
   ```

## The inventory (every env file the fleet loads — verified 2026-07-19)

| File | Loaded by | Carries | Created by |
|---|---|---|---|
| `active-profile.env` | 15 units (tetragon, zfs-arc, nvidia, ups-setup, …) | `SOVEREIGN_OS_PROFILE_ID` — the active profile pointer | first-boot / `profiles switch` (see `systemd/system/README-firstboot.md`) |
| `anthropic-key.env` | openclaw + open-computer units | `ANTHROPIC_API_KEY` (hosted-Claude backend mode only) | `sovereign-osctl {openclaw,open-computer} backend anthropic --key …` (`agent-backend.py`) |
| `openclaw.env` | sovereign-openclaw unit | gateway port, backend mode, local endpoint | `openclaw-install.sh` hook + `sovereign-osctl openclaw` |
| `open-computer.env` | sovereign-open-computer unit | sandbox backend + endpoint + ports | `open-computer-install.sh` hook + `agent-backend.py` |
| `inference-router.env` | sovereign-router | router bind/port/tier endpoints | operator / provisioning |
| `inference-pulse.env` | sovereign-pulse | Pulse model + CCD pinning overrides | `models/load.py` |
| `inference-logic-engine.env` | sovereign-logic-engine | Logic model + backend overrides | `models/load.py` |
| `inference-oracle-core.env` | sovereign-oracle-core | `ORACLE_MODEL` + quantization overrides | `inference-model-provision.sh` hook + `models/load.py` |
| `frontend-kiosk.env` | kiosk frontend unit | kiosk URL/display settings | `frontend.py` / `install-gui-dashboards.sh` |
| `ups.env` | sovereign-ups-setup | UPS host / slave-id / thresholds (APC SmartConnect) | `provision-bake.sh` |
| `notify.env` | sovereign-notify-dispatch | **all notification secrets** — ntfy base/topic/token, webhook URL, `RESEND_*`, `TWILIO_*`, operator email/SMS | operator, from [`config/notify.env.example`](https://github.com/cyberpunk042/sovereign-os/blob/main/config/notify.env.example) |

`notify.env` is the only one with a committed example file because it is the
only one whose values are ALL external-service secrets the operator must
supply by hand; the others are written by hooks/tools from operator choices.

## Setting up `notify.env` (the 2026-07-19 notification stack)

```sh
sudo install -m 0600 -o root -g root \
     /opt/sovereign-os/config/notify.env.example /etc/sovereign-os/notify.env
sudoedit /etc/sovereign-os/notify.env      # fill the real values
sudo systemctl restart sovereign-notify-dispatch.timer
```

The names it carries are exactly the ones `notify.toml` + `notifykit.toml`
reference: `SOVEREIGN_OS_NOTIFY_NTFY_{BASE_URL,TOPIC,TOKEN}`,
`SOVEREIGN_OS_NOTIFY_WEBHOOK_URL`, `RESEND_API_KEY`, `RESEND_FROM_EMAIL`,
`SOVEREIGN_OS_OPERATOR_EMAIL`, `TWILIO_{ACCOUNT_SID,AUTH_TOKEN,FROM_NUMBER}`,
`SOVEREIGN_OS_OPERATOR_SMS`.

The gating settings themselves (channel on/off, priority×urgency
thresholds, static pins, global override, trigger frontmatter props) are
NOT secrets and do NOT go here — they live in the base
`/etc/sovereign-os/notifykit.toml` + the JSON overlay the settings surface
writes (`/etc/sovereign-os/notifykit-overrides.json`).

## Anti-patterns

| Never | Because |
|---|---|
| A `.env` in the repo / a filled `*.env.example` committed | Secrets in git history are forever; SDD-030 keeps operator state out of the tree |
| Values in the TOML configs | The TOMLs are readable surface config; the `env:` indirection exists precisely so they stay shareable/committable |
| `Environment=SECRET=…` inline in a unit file | Units are world-readable under `/usr/lib`; env files carry the `0600` boundary |
| A bare `EnvironmentFile=` (no `-`) | A missing file then fails the whole unit (226/NAMESPACE-class failures at first boot) |

## Verification

```sh
ls -l /etc/sovereign-os/*.env                     # 0600 root root each
systemd-analyze cat-config systemd/system/sovereign-notify-dispatch.service | grep EnvironmentFile
sovereign-osctl notifykit show                    # gates resolve; secrets stay names
sovereign-osctl notifykit test --priority high --urgency urgent
```
