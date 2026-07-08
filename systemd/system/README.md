# systemd unit files

These are template units shipped with sovereign-os. Installation
copies them to `/etc/systemd/system/` and writes per-service env
files to `/etc/sovereign-os/inference-*.env`.

| Unit | Tier | Default port |
|---|---|---|
| `sovereign-pulse.service` | Pulse (bitnet.cpp on CCD 0) | 8081 |
| `sovereign-logic-engine.service` | Logic Engine (vLLM on 4090 VFIO) | 8082 |
| `sovereign-oracle-core.service` | Oracle Core (vLLM + DFlash on Blackwell) | 8083 |
| `sovereign-router.service` | OpenAI-compatible front | 8080 |

## Install (post-image-boot)

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
