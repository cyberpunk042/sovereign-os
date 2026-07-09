# APC Smart-UPS (SmartConnect) + graceful shutdown — operator runbook

**Our precise hardware (SAIN-01, 2026-07-08):** APC **Smart-UPS 2200VA 1980W SMT2200C**
(a *SmartConnect* model), monitored over **Modbus TCP** by **NUT's `apc_modbus`
driver**. This runbook captures exactly how we got it working — including every
dead end — so nobody re-derives it. See [SDD-026](../sdd/029-hardware-stack-consolidation.md)
for the design; this is the *how-to + troubleshooting*.

> TL;DR — it's all IaC. Packages `nut-server nut-client **nut-modbus**` + the
> `provisioning.power` block in the profile, applied by
> `scripts/install/provision.sh` (running host) or the image build
> (`provision-bake`). One command; nothing installed by hand.

---

## 1. The hardware reality that cost us the most time

The SMT2200C rear panel has **four independent management interfaces**, and two of
them are the *same RJ45 shape* — this is the #1 source of confusion:

| Rear jack | What it is | How you talk to it |
|---|---|---|
| **SmartConnect (RJ45, Ethernet)** | embedded network port | **Modbus TCP :502** (what we use) + APC cloud |
| **Serial (RJ50 / DB-9)** | classic "smart signalling" serial | Modbus RTU / apcsmart over a USB→RJ50 cable (`/dev/ttyUSB0`) |
| **USB (Type-B)** | native USB HID power device | `usbhid-ups` (vendor `051d`) |
| **SmartSlot** | add-in card bay | Network Management Card (AP9640/1) — we do NOT use one |

**Key facts we confirmed the hard way:**

- **Modbus TCP comes from the *embedded SmartConnect Ethernet port*, not a NMC.**
  Enable it on the UPS LCD: **Advanced ▸ Modbus ▸ Enable**, **TCP Protocols ▸
  Enable**, and **TCP Settings ▸ Slave ID = 1**. The port is fixed at **502**.
- **"Master IP" can be `0.0.0.0`.** That field is an allow-list; `0.0.0.0` means
  "accept any master" — it does *not* block you. (We spent time thinking it had to
  be our host IP; it doesn't.)
- **The SmartConnect Ethernet jack must be physically cabled to the LAN.** Enabling
  Modbus + TCP in the LCD does nothing until that RJ45 has link and a DHCP lease.
  The USB→RJ50 *serial* cable does **not** provide this — it goes to a different jack.
- **The UPS gets a DHCP lease like any host.** Ours: **`192.168.1.69`**, MAC
  **`28:29:86:xx:xx:xx`** (OUI = Schneider Electric / APC). **Give it a DHCP
  reservation** so the IP never drifts.

## 2. Why NUT `apc_modbus`, and not apcupsd

- **apcupsd cannot speak Modbus TCP at all** — its Modbus support is serial-only.
  A SmartConnect UPS on the network is unreachable to apcupsd.
- **NUT's `apc_modbus` driver** speaks Modbus over **TCP _and_ serial _and_ USB**,
  and is purpose-built for modern APC Smart-UPS. That's the whole reason the stack
  is NUT, not apcupsd.
- **Debian splits the driver into its own package: `nut-modbus`** (it depends on
  `libmodbus5`). `nut-server` alone ships `usbhid-ups` / `apcsmart` but **not**
  `apc_modbus`. If you install only `nut-server` + `nut-client`, you'll see
  `apc_modbus driver not found under /lib/nut` — the fix is **`apt install
  nut-modbus`** (already declared in our IaC).

## 3. How it's wired (all IaC — nothing manual)

| Layer | File | What it declares |
|---|---|---|
| Packages | `profiles/sain-01.yaml` `packages.profile` | `nut-server`, `nut-client`, **`nut-modbus`** |
| Policy | `profiles/sain-01.yaml` `provisioning.power` | `ups: apc-modbus`, `ups_host: 192.168.1.69`, `slave_id: 1`, `shutdown_minutes: 30`, `graceful_shutdown: true` |
| Running host | `scripts/install/provision.sh` (step 5) | installs deps, arms `power.toml`, enables the guard timer, runs detection |
| Image build | `scripts/build/provision-bake.sh` §7 | bakes the NUT base config + arms the guard + enables the first-boot detect unit |
| Detection | `scripts/hooks/post-install/ups-apc-setup.sh` | auto-detects transport (TCP → serial → USB-HID), writes `/etc/nut/*`, verifies via `upsc`, enables the daemons |

**Bring it up on the running host (the one command):**

```bash
scripts/install/provision.sh
# or just the UPS-relevant steps:
PROVISION_SKIP=build,dev,selfdef,rules,ghostproxy scripts/install/provision.sh
```

## 4. Detection order (the hook is idempotent + self-healing)

`ups-apc-setup.sh` tries, in order, and the first that talks wins:

1. **Idempotent short-circuit** — if NUT already talks to an APC, it's left
   *completely untouched* (no re-scan, no teardown).
2. **Reuse** — if `/etc/nut/ups.conf` already has a working stanza, it just
   **restarts NUT with it (no re-scan)**.
3. **Modbus TCP** — pinned `ups_host` first, else a bounded LAN `:502` scan,
   confirming the responder is really an APC (`device.mfr`/`model`) before latching.
4. **Serial** — `/dev/ttyUSB*` (DSD TECH USB→RJ50 cable) via `apc_modbus` serial.
5. **Native USB-HID** — vendor `051d` via `usbhid-ups`.

## 5. Verify it's live

```bash
upsc sain01ups@localhost                     # full variable dump
upsc sain01ups@localhost ups.status          # OL = online, OB = on battery, LB = low
python3 scripts/hardware/power-status.py advisories --json \
  | python3 -c "import sys,json;d=json.load(sys.stdin);t=d['thresholds'];print('verdict',d['verdict'],'| armed',t['enabled'],'| shutdown<',t['shutdown_minutes'],'min')"
systemctl is-active nut-server sovereign-power-shutdown-guard.timer
```

Healthy = `ups.status OL`, `verdict ok | armed True | shutdown< 30 min`, both `active`.
The panel is at `http://127.0.0.1:8124/` (operator-launched via `panel.sh`).

## 6. Troubleshooting — the exact symptoms we hit

| Symptom | Cause | Fix |
|---|---|---|
| Nothing on `:502` across the LAN | SmartConnect Ethernet not cabled / no DHCP lease / Modbus+TCP not enabled in LCD | Cable the RJ45; LCD ▸ Modbus + TCP Protocols Enable; check the router's DHCP table for an APC MAC (`28:29:86`, `00:c0:b7`, …) |
| `apc_modbus driver not found under /lib/nut` | `nut-modbus` package not installed (Debian split) | `apt install nut-modbus` (it's in the IaC overlay) |
| `upsc: Connection refused` | `nut-server` (upsd) not running | it's disabled/down — re-run `provision.sh` (the hook re-enables it) |
| Re-run "finds no UPS" although it worked before | **single-session** Modbus: a running driver holds the one session, so a re-scan sees `:502` as closed | fixed in the hook (idempotent + reuse-existing-stanza, no re-scan). If you hit it manually, `systemctl stop nut-driver@sain01ups`, wait ~15 s, retry |
| A raw socket probe to `:502` gives `Connection refused` right after another connection | same single-session behaviour (the UPS holds the socket in cleanup) | probe once, patiently; don't hammer it in parallel |
| `verdict` is right but `armed False` | `power.toml` not armed on this host | `provision.sh` step 5 arms it (`[graceful_shutdown] enabled = true`) |

**Confirm the UPS at the protocol level (no NUT needed):**

```bash
python3 - <<'PY'
import socket,struct
s=socket.socket(); s.settimeout(2); s.connect(("192.168.1.69",502))
s.sendall(struct.pack(">HHHBBHH",1,0,6,1,4,0,1)); print(s.recv(64).hex()); s.close()
PY
# any Modbus reply (even an exception frame) = the UPS is reachable + speaking Modbus
```

---

## 7. Graceful-shutdown orchestration (soft-exit, not a blunt poweroff)

When the UPS runtime crosses the threshold, the box does **not** just `poweroff`.
It runs an **orderly, observable soft-exit** and warns you across every medium —
"like a good system that reboots properly and doesn't disrupt the user".

### The chain

```
UPS on battery
   │  (per-minute) power-shutdown-guard.sh  ← systemd timer
   ▼
power-status.py advisories  →  verdict: ok | attention | critical
   │
   ├─ attention  (runtime ≤ shutdown_minutes + warn_lead_minutes)
   │     → graceful-warn.sh approaching  → notify(phone) · wall · console · desktop
   │       (fired ONCE per episode — dedup via /var/lib/sovereign-os/power-guard-verdict)
   │
   └─ critical + ARMED  (runtime ≤ shutdown_minutes)
         → graceful-warn.sh imminent
         → schedule-manifest.py apply  ← the STAGED soft-exit (see below)
```

### The staged soft-exit (`/etc/sovereign-os/shutdown-manifest.toml`)

Run in order, each step bounded by its own `timeout_s`, `fail_action=continue`
(except the terminal `poweroff` which aborts on failure):

1. **announce-imminent** — warn all mediums: shutdown starting.
2. **grace-window** — 45 s so an interactive operator can react.
3. **drain-inference-inflight** — [`drain-inference.sh`](../../scripts/power/drain-inference.sh) signals the router's drain flag (new completions get **503**) and **waits for in-flight LLM messages to finish** (bounded), polling `/drain-status`.
4. **stop-router** → **unload-oracle-core / -logic-engine / -pulse** → **stop-nvidia-mps** — stop the backends, **freeing GPU VRAM** cleanly.
5. **stop-dashboards** + **stop-watchers** — operator services + samplers.
6. **flush-fs-buffers** (`sync`) → **settle-metrics** (5 s).
7. **announce-final** — "powering off now" to all mediums.
8. **poweroff** — substitute `systemctl reboot` here for a planned restart.

**The router drain** ([router.py](../../scripts/inference/router.py)) is flag-gated:
absent the flag, routing is completely unchanged. During drain it 503s new
`/v1/chat/completions` and exposes `{draining, inflight}` at `/drain-status` and
`/healthz` — so in-flight requests complete instead of being cut off.

### Multi-medium warnings ([graceful-warn.sh](../../scripts/power/graceful-warn.sh))

One fan-out point, reused before (guard) and during (manifest). Stages
`approaching → imminent → executing → final`, each hitting **every** channel:

- **notify** → `sovereign-osctl notify send` → file / webhook / **ntfy (your phone)**
- **wall** → every logged-in terminal
- **/dev/console** → the physical console
- **notify-send** → desktop bubbles in active X11/Wayland sessions
- metric `sovereign_os_power_graceful_warn_total{stage,severity}`

### Preview it without shutting down

```bash
# Show exactly what a critical event would do — warnings (dry) + the full plan:
SOVEREIGN_OS_DRY_RUN=1 SOVEREIGN_OS_POWER_SHUTDOWN_ARMED=YES \
  scripts/hooks/recurrent/power-shutdown-guard.sh
# Or just the manifest:
sovereign-osctl power-shutdown plan
```

## 8. Settings — change the 30-min rule (or anything else)

Two files, both installed to `/etc/sovereign-os/` and both plain-text editable:

**`power.toml` `[graceful_shutdown]`** — *when* to warn / shut down:

| Key | Meaning | SAIN-01 |
|---|---|---|
| `enabled` | arm the auto-shutdown (else warn-only) | `true` |
| `shutdown_minutes` | fire the graceful shutdown at this runtime | `30` |
| `warn_lead_minutes` | start warning this long *before* that (→ heads-up at 45 min) | `15` |
| `battery_critical_pct` | also fire at this battery % | `15` |

**`shutdown-manifest.toml`** — *how* to shut down: the ordered steps, per-step
`timeout_s`, the 45 s grace window, service order, and **`poweroff` vs `reboot`**.
Edit a step's `cmd`/`timeout_s`, add your own `kind=shell`/`systemctl-stop` step
(services register their own soft-exit here), or swap the terminal step.

These are also set at build time from the profile's `provisioning.power`
(`shutdown_minutes`, `warn_lead_minutes`, `graceful_shutdown`).

## 9. Toggle the whole feature on/off

Good default = **on**. To build **without** UPS + graceful shutdown:

- **Profile:** set `provisioning.power.enabled: false` in `profiles/sain-01.yaml`.
- **Build configurator:** uncheck **"UPS + graceful shutdown"** (next to the bake
  toggles) — it exports `SOVEREIGN_OS_POWER_FEATURE=0`, honored by `mkosi-emit`.

Either path makes `mkosi-emit` / `provision-bake` / `provision.sh` skip the entire
NUT + guard + manifest install.
