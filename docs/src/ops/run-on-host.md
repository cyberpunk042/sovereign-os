# Managing THIS OS from the repo (single-OS workflow)

Since 2026-06-10 the operator workflow is **single-OS**: sovereign-os is
developed, tested, and *applied* on the running Debian GUI host — no
dual-boot, no reboot cycle. This page is the one runbook for that mode.

## The ⚡ YOU RUN convention

Nothing in this repo executes a mutation on its own. Every surface —
the configurator page, the panels, this doc — only **generates** commands.
A command is run exactly when *you* paste it into a terminal.

Throughout the docs and panels:

- **⚡ YOU RUN** — a command you type/paste yourself. If it needs root it
  is written with `sudo` in front; if `sudo` is absent, it never needs it.
- everything else (page rendering, probes, `/host.json`, dry-runs) is
  read-only and safe to repeat at any time.

## 0 · Start the panels (no sudo, nothing installed)

⚡ YOU RUN:

```bash
make panel          # or: scripts/operator/panel.sh
```

| URL | What it is | Mutates? |
|---|---|---|
| `http://127.0.0.1:8100/` | **Build configurator** — walk every layer; topbar button toggles `target: image build` ↔ `target: this host (live)` | only via the Run console (below) |
| `http://127.0.0.1:8100/panels` | **Index of ALL dashboards** (~43, described + categorized) | never |
| `http://127.0.0.1:8100/master-dashboard/` | **The cockpit front door** — coverage summary, control surface, described catalog, ⌘K palette, + every panel served statically | copies commands; never mutates |
| `http://127.0.0.1:8443/` | **Runtime dashboard** — live GPU / network / CPU / FS / RAID cards | never |

`Ctrl-C` in that terminal stops every panel (the live-reload broker included).

**Live-reload (on by default, SDD-203).** While `make panel` is running, editing a panel's
HTML/CSS/JS, a script it shells, or its data daemon is picked up automatically — an open
page shows a bottom-centre **"This panel updated — Refresh"** toast; click it (nothing
reloads without your consent). No stop-and-rerun. Static and shelled-script edits are a pure
refresh; an edit to a daemon's own `.py` is reloaded **in place, with no kill** (same PID).
Opt out with `SOVEREIGN_OS_LIVERELOAD=0 make panel`. It is loopback-only dev tooling — the
broker and the in-panel client are inert in the shipped image.

Every dashboard is a **control surface** — profiles, modes and feature toggles
you can drive (it copies the exact `sovereign-osctl` command; the web never
mutates). Full tour: **[The cockpit — dashboards + control surface](./cockpit.md)**.

### The Run console (the one exception to ⚡ YOU RUN)

The configurator's right panel has a **Run console** that executes
whitelisted build actions server-side and streams the log live:

- **▶ validate (dry-run)** and **▶ preflight** — work immediately, no sudo.
- **▶ BUILD image (~30 min)** — the real build. Needs root: on a GUI
  session the click pops the **system password prompt** (polkit/pkexec)
  and then runs. Headless/no-polkit fallback — start the panel elevated:

  ⚡ YOU RUN:

  ```bash
  sudo -E scripts/operator/panel.sh
  ```

  One job at a time; **■ cancel** kills it.

Host-mutating commands (systemctl, package installs, profile switches)
are never executed by any page — those stay ⚡ YOU RUN.

### Why most panels show snapshot data

`/panels` lists every webapp surface. Each is seeded with a baked
snapshot; a panel backed by a `sovereign-*-api` systemd service only goes
live once that service is installed + started (§ 2 flow, same as the hook
timers). This is by design — panels are honest about their data source
rather than blank.

In **host mode** the configurator badges every option with
<code>live ✓</code> / <code>live ✗</code> (is it ACTUALLY on this machine —
kernel config, cmdline, modules, packages, CPU flags, sovereign units) and
the right panel becomes a **Host apply plan**: numbered blocks of
⚡ YOU RUN commands that converge the host on your selections.

## 1 · Install the management CLI (first sudo)

⚡ YOU RUN (once):

```bash
sudo make install                      # sovereign-osctl → /usr/local/bin
sudo ln -sfn "$(pwd)" /opt/sovereign-os   # systemd units ExecStart from here
```

After this, `sovereign-osctl status`, `doctor`, `profiles …`, `audit …`,
`maintenance …` all work against the live host (read-only verbs stay
read-only; mutating verbs confirm or are env-gated).

## 2 · Enable recurrent hooks (pick from the configurator)

Tick the recurrent hooks you want in the configurator's host mode and
paste its generated block, or by hand, e.g.:

⚡ YOU RUN:

```bash
sudo cp systemd/system/sovereign-selfdef-sync.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now sovereign-selfdef-sync.timer
```

Hooks degrade honestly on this host: `zfs-scrub` reports *absent* while
there is no ZFS pool; GPU hooks report what `nvidia-smi` answers.

## 3 · Operator tools (declarative, dry-run first)

⚡ YOU RUN:

```bash
python3 scripts/install/operator-deps.py --deps operator-deps.toml          # report only
python3 scripts/install/operator-deps.py --deps operator-deps.toml --apply # gated apply
```

(`operator-deps.toml` is generated by the configurator's tools section.)

## 4 · Inspect / verify any time (no sudo, read-only)

⚡ YOU RUN:

```bash
sovereign-osctl status
sovereign-osctl doctor
sovereign-osctl audit drift
make test            # lint + unit + L3-fast, all green = repo healthy
```

## What deliberately does NOT run on this host (yet)

- **Image builds without root** — `orchestrate.sh run` needs sudo; use the
  Run console with an elevated panel (§ 0) or run it in a terminal.
  Output lands in `build/`.
- **Custom znver5 kernel / VFIO cmdline** — generated choices only land
  after a kernel install; the host-mode warning banner reminds you while
  the stock Debian kernel is running.
- **Cockpit data APIs** (the 84 `sovereign-*-api` units) — panels served
  statically fall back to their baked snapshots until those services are
  installed and started. Enable them the same way as the hooks in § 2,
  one at a time, when you actually want that panel live.

## Troubleshooting

- *Port busy*: `panel.sh` detects it and assumes the server is already
  running; stop strays with `pkill -f build-configurator-api` /
  `pkill -f dashboard/serve.py`.
- *`live ✗` on everything*: you are in host mode on a fresh host — that
  is the truth, not a bug. The apply plan is the path forward.
- *Page shows "data: built-in snapshot"*: you opened `index.html` from
  disk instead of via `make panel`; the live probes need the server.
