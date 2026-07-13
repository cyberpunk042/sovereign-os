# systemd unit files

These are the systemd units shipped with sovereign-os. The full fleet is
**111 units** (91 `.service` · 19 `.timer` · 1 `.target`) — the inference tier
below is only 4 of them.

## The full fleet + `make install-units`

`make install` installs the shared libraries + `sovereign-osctl` (and `make bins`
installs the Rust daemons), but **it does not install the units** — that is
`make install-units`. It stages, DESTDIR-clean:

- every `systemd/system/*.{service,timer,target}` → `/etc/systemd/system/`, and
- the three **script trees the units reference** (see the two-prefix doctrine
  below), so a booted box actually has the scripts each `ExecStart` points at.

```sh
# Stage/verify without touching the live system:
make install-units DESTDIR=/tmp/stage

# Real install (root), then activate selectively per profile:
sudo make install-units
sudo systemctl daemon-reload
sudo systemctl enable --now sovereign-gatewayd.service   # …and the units your profile needs
```

`make uninstall-units` removes the unit files + the staged script trees (disable
the units first). The Rust-daemon units (`sovereign-gatewayd.service`,
`sovereign-power-shutdown-guard.*`) are also handled by
`scripts/install/install-sovereign-root.sh` during a full root install.

### Two-prefix doctrine

A unit's `ExecStart` points at one of two script roots, by ownership:

| Script family | Install root | Units | Why this root |
|---|---|---|---|
| operator-API (`scripts/operator/…`) | `/usr/local/lib/sovereign-os/scripts/operator` | ~54 | FHS `/usr/local/lib` — the operator control-plane, installed with the rest of `PREFIX=/usr/local`. |
| hooks / inference / hardware (`scripts/{hooks,inference,hardware}/…`) | `/opt/sovereign-os/scripts/…` | ~34 | The `/opt` vendor tree the image build lays down for boot-time hooks + inference + hardware drivers. |

A handful of units call an installed binary directly (`/usr/local/bin/sovereign-gatewayd`,
`/usr/local/bin/guardian-core`) rather than a script — those come from `make bins`
/ the root installer.

`tests/lint/test_systemd_install_coverage.py` enforces this doctrine: every unit's
`ExecStart` script resolves to a real in-repo file, every referenced prefix stays
within the two documented roots, `make install-units` stages all three script
trees, and the fleet counts here match the tree — so the fleet can't grow a unit
that points at a missing script or an undocumented prefix.

## The inference tier (4 of the 111 units)

| Unit | Tier | Default port |
|---|---|---|
| `sovereign-pulse.service` | Pulse (bitnet.cpp on CCD 0) | 8081 |
| `sovereign-logic-engine.service` | Logic Engine (vLLM on 4090 VFIO) | 8082 |
| `sovereign-oracle-core.service` | Oracle Core (vLLM + DFlash on Blackwell) | 8083 |
| `sovereign-router.service` | OpenAI-compatible front | 8080 |

## Install (inference tier — env files + selective enable)

```sh
sudo cp systemd/system/*.service /etc/systemd/system/
sudo mkdir -p /etc/sovereign-os
sudo install -m 644 systemd/env.examples/inference-pulse.env /etc/sovereign-os/
sudo install -m 644 systemd/env.examples/inference-logic-engine.env /etc/sovereign-os/
sudo install -m 644 systemd/env.examples/inference-oracle-core.env /etc/sovereign-os/
sudo install -m 644 systemd/env.examples/inference-router.env /etc/sovereign-os/
sudo systemctl daemon-reload

# Enable selectively per profile:
sudo systemctl enable --now sovereign-pulse.service
sudo systemctl enable --now sovereign-logic-engine.service
sudo systemctl enable --now sovereign-oracle-core.service
sudo systemctl enable --now sovereign-router.service
```

## Per-profile activation

| Profile | Pulse | Logic | Oracle | Router |
|---|---|---|---|---|
| `sain-01` | ✓ | ✓ | ✓ | ✓ |
| `old-workstation` | — | ✓ (llama.cpp backend) | — | ✓ (optional) |
| `minimal` / `headless` | — | — | — | — |
| `developer` (reserved) | optional | ✓ | — | optional |

## Security posture

All four units:
- `NoNewPrivileges=true`
- `ProtectSystem=strict` + explicit `ReadWritePaths=` for logs + state
- `ReadOnlyPaths=/mnt/vault/models`
- `PrivateTmp=true`

`sovereign-router.service` adds `DynamicUser=true` (router needs no
identity beyond network access). Backend services run as root
because GPU + VFIO + container management requires privilege; tighter
isolation lands when each backend ships with a dedicated user
(Stage-2 next round).

## Ordering

`tetragon.service` is `Required` by Logic Engine + Oracle Core: no
inference starts before the kernel perimeter is loaded. This is the
SAIN-01 Trinity contract (Auditor before Pulse/Weaver).

Router has `Wants=` (not `Requires=`) on the three backends — it
gracefully reports per-tier 502 if one isn't up, rather than failing
the whole router.
