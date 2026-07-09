# APC Smart‑UPS (SmartConnect) + Graceful Shutdown — Operator Guide

Live UPS monitoring and an **orderly, warned, staged shutdown** for SAIN‑01, over
**Modbus TCP** using **NUT's `apc_modbus`** driver. This is the definitive how‑to +
reference: how it's wired, how to run/verify/tune it, every dead end we hit and
its fix, and the design behind the soft‑exit. Design lineage: [SDD‑029 —
hardware‑stack‑consolidation](../sdd/029-hardware-stack-consolidation.md) (R252
power‑status · R253 shutdown‑guard · R262 schedule‑manifest · R228 notify).

**Our hardware (verified 2026‑07‑08):** APC **Smart‑UPS 2200VA 1980W SMT2200C**
(a *SmartConnect* model), at DHCP **`192.168.1.69`**, MAC **`28:29:86:…`**
(Schneider/APC), Modbus TCP on **:502**, slave id **1**.

> **TL;DR** — It's all IaC. The profile declares the packages
> (`nut-server nut-client nut-modbus`) + a `provisioning.power` block; one command
> (`scripts/install/provision.sh`, or the image build) installs, arms, and
> self‑detects. Nothing is installed by hand. When the UPS runtime drops below
> **30 min** the box warns you everywhere and runs a **14‑step soft‑exit** (drain
> inference → finish in‑flight LLM messages → unload models → stop services → sync
> → poweroff) instead of a blunt `poweroff`.

---

## Contents

1. [System at a glance](#1-system-at-a-glance) · [Component map](#component-map)
2. [The hardware — SMT2200C rear panel](#2-the-hardware--smt2200c-rear-panel)
3. [Why NUT `apc_modbus`, not apcupsd](#3-why-nut-apc_modbus-not-apcupsd)
4. [How it's wired (all IaC)](#4-how-its-wired-all-iac)
5. [Detection — the self‑healing hook](#5-detection--the-self-healing-hook)
6. [Graceful shutdown — the staged soft‑exit](#6-graceful-shutdown--the-staged-soft-exit)
7. [Verify it's live](#7-verify-its-live)
8. [Tune the settings (the 30‑min rule & more)](#8-tune-the-settings)
9. [Toggle the whole feature on/off](#9-toggle-the-whole-feature-onoff)
10. [Observe — metrics, panel, alerts](#10-observe--metrics-panel-alerts)
11. [Troubleshooting](#11-troubleshooting)
12. [Operator‑CLI freshness (the drift trap)](#12-operator-cli-freshness-the-drift-trap)
13. [Lessons learned](#13-lessons-learned)
14. [Quick‑reference card](#14-quick-reference-card)

---

## 1. System at a glance

```
   ┌── HARDWARE ──────────────┐        ┌── MONITORING ─────────────────────────┐
   │  APC SMT2200C            │ Modbus │  nut-driver@sain01ups (apc_modbus)     │
   │  SmartConnect RJ45 :502  │──TCP──▶ │       │                               │
   │  MAC 28:29:86 → .69      │        │       ▼   upsd (127.0.0.1:3493)        │
   └──────────────────────────┘        │   upsc ◀── power-status.py advisories  │
                                        └───────────────────┬───────────────────┘
                                                            │ verdict: ok/attention/critical
   ┌── TRIGGER (per-minute timer) ──────────────────────────▼───────────────────┐
   │  power-shutdown-guard.sh                                                    │
   │     attention → graceful-warn.sh approaching  (warn once, minutes ahead)    │
   │     critical + armed ─────────────────────────────────────┐                 │
   └──────────────────────────────────────────────────────────┼─────────────────┘
                                                               ▼
   ┌── SOFT-EXIT (schedule-manifest apply) ──────────────────────────────────────┐
   │  announce → grace → DRAIN inference (finish in-flight) → stop router →       │
   │  UNLOAD models (free VRAM) → stop services → sync → final warn → poweroff    │
   └─────────────────────────────────────────────────────────────────────────────┘
                                                               │  at every stage:
   ┌── WARN (all mediums, before + during) ──────────────────▼───────────────────┐
   │  notify send → file / webhook / ntfy(phone)  ·  wall  ·  /dev/console  ·     │
   │  desktop notify-send  ·  UPS panel banner + countdown (:8124)                │
   └─────────────────────────────────────────────────────────────────────────────┘
```

**What it does, in one paragraph.** A NUT `apc_modbus` driver polls the UPS over
Modbus TCP; `power-status.py` turns that into a verdict (`ok`/`attention`/
`critical`). A per‑minute guard warns you across every channel as runtime gets
low, and — once runtime crosses the armed threshold — runs a staged, timeout‑bounded
soft‑exit that quiesces inference (letting in‑flight LLM requests finish), unloads
models to free VRAM, stops services in order, flushes disks, and only then powers
off. Every threshold and every step is operator‑editable; the whole feature is a
build toggle.

### Component map

| File | Round | Role | Runs where |
|---|---|---|---|
| [`scripts/hooks/post-install/ups-apc-setup.sh`](../../scripts/hooks/post-install/ups-apc-setup.sh) | — | **Detect** the transport (TCP→serial→USB‑HID), write `/etc/nut/*`, verify via `upsc`, enable daemons | first boot + `provision.sh` |
| [`scripts/hardware/power-status.py`](../../scripts/hardware/power-status.py) | R252 | Read `upsc` → **verdict** + thresholds (`ups`/`advisories` verbs) | on demand + guard |
| [`scripts/hooks/recurrent/power-shutdown-guard.sh`](../../scripts/hooks/recurrent/power-shutdown-guard.sh) | R253 | **Trigger**: per‑minute; warn on attention, orchestrate on critical+armed | `sovereign-power-shutdown-guard.timer` |
| [`scripts/power/schedule-manifest.py`](../../scripts/power/schedule-manifest.py) | R262 | **Orchestrate**: run the staged soft‑exit (`list`/`plan`/`apply`) | invoked by the guard |
| [`config/shutdown-manifest.toml.example`](../../config/shutdown-manifest.toml.example) | R262 | The **staged sequence** (14 steps) → `/etc/sovereign-os/shutdown-manifest.toml` | — |
| [`scripts/power/graceful-warn.sh`](../../scripts/power/graceful-warn.sh) | — | **Warn** all mediums (notify/wall/console/desktop) — staged | guard + manifest |
| [`scripts/power/drain-inference.sh`](../../scripts/power/drain-inference.sh) | — | **Drain**: signal router drain + wait for in‑flight → 0 | manifest step |
| [`scripts/inference/router.py`](../../scripts/inference/router.py) | — | Flag‑gated **drain mode** (`/drain-status`, 503 new completions) | `sovereign-router.service` |
| [`scripts/notify/dispatch.py`](../../scripts/notify/dispatch.py) | R228 | Notify fan‑out incl. the `send` verb → file/webhook/ntfy | on demand |
| [`config/power.toml.example`](../../config/power.toml.example) | R252 | **Thresholds** (`[graceful_shutdown]`) → `/etc/sovereign-os/power.toml` | — |
| [`webapp/ups/index.html`](../../webapp/ups/index.html) | — | Panel: live state + shutdown‑imminent banner + countdown (:8124) | `sovereign-ups-api` |
| [`profiles/sain-01.yaml`](../../profiles/sain-01.yaml) | — | Declares packages + `provisioning.power` (the master toggle + policy) | build/provision |

---

## 2. The hardware — SMT2200C rear panel

The rear panel has **four independent management interfaces**, and two are the
*same RJ45 shape* — the #1 source of confusion:

| Rear jack | What it is | How you talk to it |
|---|---|---|
| **SmartConnect (RJ45, Ethernet)** | embedded network port | **Modbus TCP :502** ← *we use this* · + APC cloud |
| **Serial (RJ50 / DB‑9)** | classic "smart signalling" serial | Modbus RTU / apcsmart over a USB→RJ50 cable (`/dev/ttyUSB0`) |
| **USB (Type‑B)** | native USB HID power device | `usbhid-ups` (vendor `051d`) |
| **SmartSlot** | add‑in card bay | Network Management Card (AP9640/1) — *not used* |

**Facts we confirmed the hard way:**

- **Modbus TCP is served by the embedded SmartConnect port — no NMC needed.**
  On the UPS LCD: **Advanced ▸ Modbus ▸ Enable**, **TCP Protocols ▸ Enable**,
  **TCP Settings ▸ Slave ID = 1**. Port is fixed at **502**.
- **"Master IP" can be `0.0.0.0`** — it's an allow‑list; `0.0.0.0` = accept any
  master. It does *not* have to be our host IP.
- **The SmartConnect RJ45 must be physically cabled to the LAN.** Enabling
  Modbus + TCP in the LCD does nothing until that jack has link + a DHCP lease.
  The USB→RJ50 *serial* cable is a **different jack** — it does not provide this.
- **The UPS gets a DHCP lease like any host** → **reserve it** (MAC `28:29:86:…`
  → `.69`) so the pinned IP never drifts.

## 3. Why NUT `apc_modbus`, not apcupsd

- **apcupsd cannot speak Modbus TCP** — its Modbus support is serial‑only. A
  SmartConnect UPS on the network is invisible to apcupsd.
- **NUT `apc_modbus`** speaks Modbus over **TCP *and* serial *and* USB** — purpose‑
  built for modern APC Smart‑UPS. That's why the stack is NUT.
- **Debian ships the driver in a *separate* package: `nut-modbus`** (depends on
  `libmodbus5`). `nut-server` alone ships `usbhid-ups`/`apcsmart` but **not**
  `apc_modbus`. Symptom of missing it: `apc_modbus driver not found under /lib/nut`.
  Fix: `apt install nut-modbus` — already declared in our IaC.

## 4. How it's wired (all IaC)

| Layer | File | What it does |
|---|---|---|
| Packages | `profiles/sain-01.yaml` `packages.profile` | `nut-server`, `nut-client`, **`nut-modbus`** |
| Policy / toggle | `profiles/sain-01.yaml` `provisioning.power` | `enabled`, `ups: apc-modbus`, `ups_host: 192.168.1.69`, `slave_id: 1`, `shutdown_minutes: 30`, `warn_lead_minutes: 15`, `graceful_shutdown: true` |
| Running host | `scripts/install/provision.sh` (step 5) | install deps, arm `power.toml`, install manifest, enable guard timer, run detection |
| Image build | `scripts/build/provision-bake.sh` §7 | bake NUT base + power.toml + manifest + enable first‑boot detect unit |
| Env plumbing | `scripts/build/adapters/mkosi-emit.sh` | profile `provisioning.power` → `SOVEREIGN_OS_UPS*` env for the bake |

**Bring it up on the running host — one command (idempotent):**

```bash
scripts/install/provision.sh
# or just the UPS-relevant steps (skip the heavy build/dev steps):
PROVISION_SKIP=build,dev,selfdef,rules,ghostproxy scripts/install/provision.sh
```

## 5. Detection — the self‑healing hook

`ups-apc-setup.sh` tries these in order; **first that talks wins**. It is
idempotent and safe to re‑run (a lesson paid for in blood — see §13):

1. **Idempotent short‑circuit** — if NUT already talks to an APC, leave it
   *entirely untouched* (no re‑scan, no teardown).
2. **Reuse** — if `/etc/nut/ups.conf` already has a working stanza, just
   **restart NUT with it** (no re‑scan → dodges the single‑session trap).
3. **Modbus TCP** — pinned `ups_host` first, else a bounded LAN `:502` scan,
   confirming the responder is really an APC (`device.mfr`/`model`) before latching.
4. **Serial** — `/dev/ttyUSB*` (DSD TECH USB→RJ50) via `apc_modbus` serial.
5. **Native USB‑HID** — vendor `051d` via `usbhid-ups`.

## 6. Graceful shutdown — the staged soft‑exit

When runtime crosses the armed threshold the box does **not** `poweroff` bluntly.
It runs an orderly, observable soft‑exit — *"a good system that reboots properly
and doesn't disrupt the user."*

### The decision (per‑minute guard)

```
power-status.py advisories → verdict
   ok         → nothing
   attention  → graceful-warn.sh approaching   (once per episode; dedup file)
                 └ runtime ≤ shutdown_minutes + warn_lead_minutes
   critical + ARMED → graceful-warn.sh imminent → schedule-manifest.py apply
                 └ runtime ≤ shutdown_minutes
```

Re‑entry is locked (`/run/sovereign-os/shutdown-in-progress`) so the minutely
timer can't restack a shutdown already underway.

### The staged sequence (`/etc/sovereign-os/shutdown-manifest.toml`)

14 steps, each bounded by `timeout_s`, `fail_action=continue` (the terminal
`poweroff` aborts on failure):

```
 0 announce-imminent        warn all mediums: shutdown starting
 1 grace-window        45s  interactive operators react
 2 drain-inference     60s  503 new completions; WAIT for in-flight LLM msgs → 0
 3 stop-router              no more proxying
 4 unload-oracle-core       ┐
 5 unload-logic-engine      ├ stop backends → FREE GPU VRAM cleanly
 6 unload-pulse             │
 7 stop-nvidia-mps          ┘
 8 stop-dashboards          ┐
 9 stop-watchers            ┘ operator services + samplers
10 flush-fs-buffers    sync
11 settle-metrics       5s  let Layer-B metric emission settle
12 announce-final           warn all mediums: powering off now
13 poweroff                 ← swap for `systemctl reboot` for a planned restart
```

**In‑flight LLM finishing** — the [router](../../scripts/inference/router.py) has a
**flag‑gated** drain: absent the flag, routing is unchanged. During drain it 503s
new `/v1/chat/completions` and exposes `{draining, inflight}` at `/drain-status`
and `/healthz`; [`drain-inference.sh`](../../scripts/power/drain-inference.sh)
signals it and polls until in‑flight reaches 0 (or the deadline) — so live requests
*complete* instead of being cut.

### Warnings — every medium, before + during

[`graceful-warn.sh`](../../scripts/power/graceful-warn.sh) is one fan‑out point,
reused by the guard (before) and the manifest (during). Stages
`approaching → imminent → executing → final`, each hitting:

- **notify** → `sovereign-osctl notify send` → file / webhook / **ntfy (phone)**
- **wall** → every logged‑in terminal · **/dev/console** → physical console
- **notify‑send** → desktop bubbles in active X11/Wayland sessions
- **UPS panel** → red "shutdown imminent" banner + countdown (`:8124`)

### Preview it without shutting down

```bash
# full decision + warnings (dry) + the exact plan — NO poweroff:
SOVEREIGN_OS_DRY_RUN=1 SOVEREIGN_OS_POWER_SHUTDOWN_ARMED=YES \
  scripts/hooks/recurrent/power-shutdown-guard.sh
sovereign-osctl power-shutdown plan        # just the manifest
```

## 7. Verify it's live

```bash
upsc sain01ups@localhost                    # full variable dump
upsc sain01ups@localhost ups.status         # OL=online  OB=on-battery  LB=low
python3 scripts/hardware/power-status.py advisories --json \
  | python3 -c "import sys,json;d=json.load(sys.stdin);t=d['thresholds'];print('verdict',d['verdict'],'| armed',t['enabled'],'| shutdown<',t['shutdown_minutes'],'| warn<',t['warn_at_minutes'],'min')"
systemctl is-active nut-server sovereign-power-shutdown-guard.timer
```

**Healthy** = `ups.status OL` · `armed True · shutdown< 30 · warn< 45 min` · both
`active`. Panel: `http://127.0.0.1:8124/` (operator‑launched via `panel.sh`).

## 8. Tune the settings

Two plain‑text files under `/etc/sovereign-os/`:

**`power.toml` `[graceful_shutdown]`** — *when* to warn / shut down:

| Key | Meaning | SAIN‑01 |
|---|---|---|
| `enabled` | arm auto‑shutdown (else warn‑only) | `true` |
| `shutdown_minutes` | fire the soft‑exit at this runtime | `30` |
| `warn_lead_minutes` | begin warning this long *before* that (→ heads‑up at 45 min) | `15` |
| `battery_critical_pct` | also fire at this battery % | `15` |

> The effective warn threshold is `max(runtime_warn_minutes, shutdown_minutes +
> warn_lead_minutes)` — so warnings **always** precede the shutdown, even with an
> aggressive `shutdown_minutes`. (The old default warned *after* the shutdown fired.)

**`shutdown-manifest.toml`** — *how* to shut down: the ordered steps, each
`timeout_s`, the 45 s grace window, service order, and **`poweroff` vs `reboot`**.
Edit a step, add your own (`kind=shell` / `systemctl-stop`) so a service registers
its own soft‑exit, or swap the terminal step. Validate after editing:
`sovereign-osctl power-shutdown list`.

Both are also set at build time from the profile's `provisioning.power`.

## 9. Toggle the whole feature on/off

Good default = **on**. To build **without** UPS + graceful shutdown:

- **Profile:** `provisioning.power.enabled: false` in `profiles/sain-01.yaml`.
- **Build configurator:** uncheck **"UPS + graceful shutdown"** (by the bake
  toggles) → exports `SOVEREIGN_OS_POWER_FEATURE=0`, honored by `mkosi-emit`.

Either path makes `mkosi-emit` / `provision-bake` / `provision.sh` skip the entire
NUT + guard + manifest install.

## 10. Observe — metrics, panel, alerts

| Metric | Meaning |
|---|---|
| `sovereign_os_power_shutdown_guard_verdict` | 0=ok 1=attention 2=critical 3=no‑ups 9=error — **alert on →2** |
| `sovereign_os_power_shutdown_guard_fired` | `1` iff a real soft‑exit fired — **alert on ==1** |
| `sovereign_os_power_graceful_warn_total{stage,severity}` | warnings fanned per stage |
| `sovereign_os_power_drain_inference_total{result}` | drain outcome (drained/timeout/no‑router) |

Plus live UPS variables via NUT (`battery.charge`, `battery.runtime`, `ups.status`,
`ups.load`, `ups.realpower`). Panel `:8124` renders them + the imminent banner. Full list: the
[metric inventory](../observability/dashboards/README.md).

## 11. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Nothing on `:502` across the LAN | SmartConnect RJ45 not cabled / no DHCP lease / Modbus+TCP not enabled in LCD | Cable the RJ45; LCD ▸ Modbus + TCP Protocols; check the router DHCP table for an APC MAC (`28:29:86`, `00:c0:b7`, …) |
| `apc_modbus driver not found under /lib/nut` | `nut-modbus` not installed (Debian split) | `apt install nut-modbus` (it's in the IaC overlay) |
| `upsc: Connection refused` | `nut-server` (upsd) not running | re‑run `provision.sh` — the hook re‑enables it |
| Re‑run "finds no UPS" though it worked before | **single‑session** Modbus: a running driver holds the one session, so a re‑scan sees `:502` closed | fixed in the hook (idempotent + reuse). Manual: `systemctl stop nut-driver@sain01ups`, wait ~15 s, retry |
| Raw `:502` probe gives `Connection refused` right after another connection | same single‑session cleanup window | probe once, patiently; never in parallel |
| `verdict` right but `armed False` | `power.toml` not armed on this host | `provision.sh` step 5 arms it (`enabled = true`) |
| `sovereign-osctl power-shutdown: schedule-manifest.py: No such file` | stale installed CLI (see §12) | `sudo scripts/install/link-operator-cli.sh` |

**Confirm the UPS at the protocol level (no NUT needed):**

```bash
python3 - <<'PY'
import socket, struct
s = socket.socket(); s.settimeout(2); s.connect(("192.168.1.69", 502))
s.sendall(struct.pack(">HHHBBHH", 1, 0, 6, 1, 4, 0, 1)); print(s.recv(64).hex()); s.close()
PY
# any Modbus reply (even an exception frame) = UPS reachable + speaking Modbus
```

## 12. Operator‑CLI freshness (the drift trap)

`make install` copies `sovereign-osctl` → `/usr/local/bin` and the tree →
`/usr/local/lib/sovereign-os`. On a **dev host** the repo keeps changing, so that
copy silently goes stale — a month‑old copy made `sovereign-osctl power-shutdown`
fail with `schedule-manifest.py: No such file`. Fix + prevention (all IaC):

- The osctl now resolves through symlinks (`readlink -f`), so a symlinked
  entrypoint locates the *real* working tree.
- [`scripts/install/link-operator-cli.sh`](../../scripts/install/link-operator-cli.sh)
  live‑links `/usr/local/bin/sovereign-osctl` + `/usr/local/lib/sovereign-os` → the
  repo (idempotent). `provision.sh` runs it every time; a live‑repo
  `install-gui-dashboards.sh` symlinks instead of copying.

```bash
sudo scripts/install/link-operator-cli.sh   # repair a stale install anytime
```

## 13. Lessons learned

- **Identical RJ45 jacks lie.** SmartConnect (Ethernet/Modbus‑TCP) ≠ the serial
  jack. Cable the right one; enabling Modbus in the LCD isn't enough.
- **apcupsd ≠ Modbus TCP.** SmartConnect on the network needs NUT `apc_modbus`.
- **`nut-modbus` is a separate Debian package.** `nut-server` alone isn't enough.
- **APC Modbus TCP is single‑session.** One connection at a time, held in cleanup
  for seconds. Never parallel‑scan; never re‑scan when a driver already talks — the
  hook now reuses the existing stanza instead.
- **Warn *before* the shutdown, not after.** `warn_lead_minutes` makes the
  attention verdict fire above the shutdown threshold.
- **Deployed copies drift.** On a dev host, symlink the CLI/lib to the repo.

## 14. Quick‑reference card

```bash
# ── status ──────────────────────────────────────────────────────────────
upsc sain01ups@localhost                         # full UPS variable dump
upsc sain01ups@localhost ups.status              # OL / OB / LB
sovereign-osctl power-status ups --json          # power-status view
python3 scripts/hardware/power-status.py advisories --json   # verdict + thresholds
systemctl is-active nut-server sovereign-power-shutdown-guard.timer

# ── graceful shutdown (safe, non-destructive) ───────────────────────────
sovereign-osctl power-shutdown plan              # preview the staged sequence
SOVEREIGN_OS_DRY_RUN=1 SOVEREIGN_OS_POWER_SHUTDOWN_ARMED=YES \
  scripts/hooks/recurrent/power-shutdown-guard.sh   # full decision, dry
sovereign-osctl notify send --message "test" --severity down --dry-run

# ── manage / repair ─────────────────────────────────────────────────────
PROVISION_SKIP=build,dev,selfdef,rules,ghostproxy scripts/install/provision.sh
sudo scripts/install/link-operator-cli.sh        # refresh a stale operator CLI
sudo bash scripts/hooks/post-install/ups-apc-setup.sh   # re-detect the UPS

# ── settings ────────────────────────────────────────────────────────────
sudoedit /etc/sovereign-os/power.toml            # thresholds (30-min rule, warn lead)
sudoedit /etc/sovereign-os/shutdown-manifest.toml # the staged sequence (poweroff↔reboot)
```
