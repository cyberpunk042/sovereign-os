# SDD-203 — Live-reload for the dev operator panels (self-re-exec + SSE refresh-notify)

> Status: **complete** — broker + self-re-exec launcher + in-panel client shipped, wired into BOTH `make panel` (dev) AND the flashed image (systemd), ON by default; toggle off with `bake.livereload:false` / `SOVEREIGN_OS_LIVERELOAD=0`.
> Owner: operator-supervised; agent-authored
> Last updated: 2026-07-11
> Closes findings: E11.M203 (mandate decomposition — dev-panel live-reload)
> Builds ON SDD-067 (the app-shell block that ships byte-identical into every adopted
> panel — the natural, contract-guarded home for the in-panel client) and the
> `scripts/operator/panel.sh` dev launcher. Fourth SDD in the header-sidemenu
> session's **200-band** (per SDD-100 parallel-session conflict avoidance).

## 0. Operator directive (verbatim)

> "couldn't there be a live-reload feature now that I think about it that is enabled by
> default ? so that I dont have to redo make panel everytime. one way that doesn't even
> need to kill anything if possible ? aren't those static assets ? in the page if a panel
> has updated there could be a notification at the bottom center and offer to refresh the
> page. and we dont reload something for nothing I guess but the reload include the
> services / apis behind. no matter how complex and long we can take the time. no rush, do
> this right and performant"

## 1. Mission

Iterating on a panel required stopping (`Ctrl-C`) and re-running — under `make panel` in dev,
or `systemctl restart` on an installed box. This SDD removes that loop **on both surfaces**:
**an edit is picked up automatically, and each open panel offers a refresh** — with no manual
kill, no reload "for nothing", and coverage of the services/APIs behind the page, not just the
static assets. The operator keeps developing on the **live `/opt/sovereign-os` checkout after
the box is flashed** (the systemd services run it via the `/usr/local/lib/sovereign-os →
/opt/sovereign-os` symlink), not only under `make panel`. Shipped ON by default; a locked,
non-dev image sets `bake.livereload:false`.

## 2. Problem — three kinds of change, only one needs a restart

The panel daemons (`scripts/operator/*-api.py`) already read their HTML fresh
(`WEBAPP.read_bytes()`) and re-run the scripts they surface **on every request**. So:

| What changed | What the running process needs | Restart? |
|---|---|---|
| a panel's `webapp/<slug>/` HTML/CSS/JS | nothing — read fresh next request | **no** |
| a script the daemon shells (`science.py`, `power-status.py`, …) | nothing — re-run next request | **no** |
| the daemon's OWN `-api.py` source | new code loaded into the process | yes — but can be in-place |

So the common case ("aren't those static assets?") is a pure **browser refresh**; only a
daemon's own `.py` genuinely needs new code in the process — and even that is done
**in place, with no kill** (the operator's "doesn't even need to kill anything").

## 3. Design — three decoupled parts

### 3.1 `scripts/operator/lib/reload-run.py` — self-re-exec launcher (no-kill)
`make panel` launches every daemon THROUGH this wrapper. It runs the target via
`runpy.run_path(..., run_name="__main__")` **in the same process** (so the daemon keeps
its PID and owns its listening socket) and watches the daemon's own source + any repo-local
modules it imports. On a real edit it `os.execv`s itself — **the same process image is
replaced** (same PID, no external kill, no `Ctrl-C`); the socket is closed by `execv` and
instantly re-bound (`http.server` sets `allow_reuse_address`), so the port gap is a few ms.
A newly-appeared file (a lazy import settling in — e.g. the hub imports `urllib` inside
`_proxy` on first request) is absorbed silently, never triggering a bounce mid-request. A
crashed daemon (e.g. a syntax error) is kept recoverable: the non-daemon watcher outlives it
and re-execs on the next save. Disabled (`SOVEREIGN_OS_LIVERELOAD=0`) it is a transparent
pass-through, behaviourally identical to `python3 <target>`.

### 3.2 `scripts/operator/livereload-broker.py` — one watcher, SSE fan-out
A single lightweight file-watcher for the WHOLE fleet (not one per daemon — "performant"),
bound loopback-only on **:8136**. It scans `webapp/`+`scripts/`+`config/` mtimes and pushes
an `event: reload` over Server-Sent Events. **"Never for nothing"**: at startup it parses
each daemon once (stdlib-only, no YAML) for the `webapp/<slug>` it serves + the
`scripts/…`/`config/…` it shells, so a panel is notified ONLY for paths it depends on — its
own `webapp/<slug>/`, the shared chrome (`webapp/_shared/`), its daemon source, and that
daemon's shelled scripts. An unrelated edit stays silent. It is read-only and never leaves
127.0.0.1; it is a DEV tool — not shipped/enabled in the image.

### 3.3 In-panel client — bottom-centre refresh toast
A small `EventSource` client lives in the SDD-067 app-shell block
(`webapp/_shared/app-shell-snippet.html`), so `sync-app-shell.py` distributes it
byte-identically to every adopted panel and the app-shell contract keeps it honest. It is:
- **loopback-gated** — no-ops unless the page host is `127.0.0.1`/`localhost`, and gives up
  quietly after a few failed connects, so it is **inert in the shipped image**;
- **read-only + non-mutating** — a GET `EventSource` + a `location.reload()` (navigation),
  consistent with the chrome's "navigates + explains, never executes" charter (no
  `fetch`/XHR/POST/sendBeacon — the app-shell non-mutation contract stays green);
- **precise** — it shows a bottom-centre "This panel updated — **Refresh**" toast (with a
  dismiss) only on a broker-scoped relevant change, coalescing a burst into one toast.

The client's slug reaches the broker two ways so it works on BOTH serving paths: hub-served
pages (`:8100/<slug>/`) send `panel=<slug>` parsed from the path; own-port pages (`:81xx/`,
where the standalone panels — science/ups/flash/emulate — serve their own live data) send
`port=<n>` and the broker maps port → slug.

### 3.4 `make panel` wiring (dev)
`panel.sh` starts the broker first, then launches the two main servers + every panel daemon
through `reload-run.py`. **On by default**; opt out with `SOVEREIGN_OS_LIVERELOAD=0`. The
broker is NOT wrapped (it holds live SSE connections a re-exec would drop; clients
auto-reconnect anyway). Cleanup kills the broker with the rest; `takeover_port` reclaims it
on the next run.

### 3.5 The flashed image (systemd) — same feature, on by default
On an installed box the panel APIs run as `sovereign-*-api.service` (not `make panel`), so the
wiring is materialised at provision time (`scripts/build/provision-bake.sh` §5c on the mkosi
image path; `scripts/install/install-gui-dashboards.sh` §3c on the root-reflash/standalone
path), gated on `SOVEREIGN_OS_BAKE_LIVERELOAD` (default ON; `profiles/*.yaml`
`provisioning.bake.livereload`):
- `sovereign-livereload-broker.service` (NEW, R171-hardened, loopback :8136) is enabled — it
  watches the live `/opt/sovereign-os` tree and offers open panels a refresh. Webapp and
  shelled-script edits already take effect on the next request (the daemons read fresh), so
  those become a **pure refresh with no service change at all**.
- Each ENABLED panel API + the hub gets a systemd **drop-in**
  (`/etc/systemd/system/<unit>.d/livereload.conf`) that sets `SOVEREIGN_OS_LIVERELOAD=1` and
  overrides `ExecStart` to run through `reload-run.py`. So an edit to a daemon's OWN `.py`
  re-execs it **in place — same PID, no `systemctl restart`, no kill**. The **shipped unit
  files stay byte-identical** (the override lives only in the generated drop-in), so every
  per-unit ExecStart/hardening lint is untouched. `os.execv` preserves the MainPID, so systemd
  never sees a restart. A locked build (`bake.livereload:false`) generates no drop-ins and
  omits the broker → the units run their original ExecStart and the in-panel client falls inert.

## 4. Coverage / verification

- **Broker SSE** — a relevant edit (`webapp/science/index.html`) delivers `event: reload` to
  the science client; an **irrelevant** edit (`webapp/ups/index.html`) delivers nothing
  ("never for nothing"). (`tests/nspawn/test_live_reload.sh`, `tests/lint/…`.)
- **Self-re-exec** — a daemon edited under `reload-run.py` serves fresh code with the **same
  PID** and no manual restart (true in-place re-exec, no kill).
- **Static contract** — `tests/lint/test_live_reload_contract.py`: client present in the
  app-shell + loopback-gated + `EventSource`-only (no fetch/XHR/POST), broker/port
  consistency (8136, no unit collision), both daemons compile + carry shebangs, `panel.sh`
  routes through `reload-run.py` + starts the broker + defaults on.
- **App-shell non-mutation** — `tests/lint/test_app_shell_contract.py` still green (the
  `EventSource` client adds no `fetch`).

## 5. Non-goals

- **Remote/LAN live-reload.** The broker binds loopback only and the in-panel client is
  loopback-gated, so live-reload works when developing **on the box** (its own GUI, browsing
  127.0.0.1) — the intended flow. Exposing the panels (or the broker) beyond loopback stays a
  deliberate, separate operator decision (the per-unit `…_BIND` override), not this SDD.
- **HMR / stateful hot-patching.** No module-level state is preserved across a daemon
  reload — the daemons are stateless read fronts, so a clean re-exec is correct and simplest.
- **Auto-refresh without consent.** The page is never reloaded automatically — the operator
  is *offered* a refresh (their "offer to refresh the page"), preserving in-progress work.
- **Live-reload on a locked/appliance build.** `bake.livereload:false` omits the broker + the
  drop-ins entirely; the client then finds no broker and falls inert.

## 6. Cross-references

- SDD-067 — app-shell block + `sync-app-shell.py` (the client's distribution surface).
- `scripts/operator/panel.sh` — the dev launcher this extends.
- `scripts/operator/lib/reload-run.py`, `scripts/operator/livereload-broker.py` — the
  self-re-exec launcher + the broker.
- `systemd/system/sovereign-livereload-broker.service` — the shipped broker unit.
- `scripts/build/provision-bake.sh` §5c + `scripts/install/install-gui-dashboards.sh` §3c —
  the installed-box wiring (broker enable + reload-run ExecStart drop-ins), gated on
  `SOVEREIGN_OS_BAKE_LIVERELOAD` (mkosi-emit → `profiles/*.yaml` `provisioning.bake.livereload`).
- CHANGELOG Round 559.
