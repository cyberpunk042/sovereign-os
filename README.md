# sovereign-os

**Build YOUR sovereign AI workstation OS from a Debian-13 starting point.**
Custom kernel (Zen 5 native AVX-512), ZFS-tiered storage, VFIO-isolated GPUs,
Tetragon kernel-level perimeter, BitNet 1-bit inference + DeepSeek/Qwen/Ling on
twin GPUs — all built from spec, all reproducibly, all yours.

> **For the AI workstation operator** (SAIN-01 by default; 4 other profiles
> shipped). Read this if you cloned the repo and want to know:
> *what is this?*, *is it for me?*, *what do I type first?*

---

## What you build, in plain English

A bootable disk image that, when written to your SAIN-01 hardware,
gives you a **Sovereign AI Node** — the architecture from the master
spec at [`docs/src/sain-01-master-spec.md`](docs/src/sain-01-master-spec.md):

> CPU: AMD Ryzen 9 9900X · Zen 5 · single-cycle 512-bit AVX-512.
> GPUs: RTX PRO 6000 Blackwell Max-Q (96GB, 300W) + RTX 4090 (24GB VFIO).
> Storage: 2× NVMe PCIe 5.0 in ZFS RAID-0, tiered datasets.
> Networking: 10GbE data + 2.5GbE mgmt, VLAN-asymmetric.
> Software trinity: **Pulse** (Wasm-to-AVX-512 AOT + BitNet ternary)
> · **Weaver** (Podman + VFIO + atomic state on tank/context)
> · **Auditor** (Tetragon eBPF + Guardian Daemon).

It runs Debian 13 (Trixie) at the base — Debian is the Ark; sovereign-os
is everywhere you depart from it. Operator-owned signing chain.
Reproducible builds (same inputs → same bytes). No phone-home defaults.
Layer A/B/C observability without Grafana/Alertmanager required.

If you don't have SAIN-01 hardware, you can still build:
- `old-workstation` (constrained dev box: single 4090, ext4)
- `minimal` (VM baseline, useful for trying the pipeline)
- `developer` (polyglot dev workstation)
- `headless` (bare-metal server with auditd/fail2ban/chrony)

---

## Is this for me?

Yes if:
- you want to **own and customize every layer** of your AI workstation OS
- you accept that "build your own kernel" is a 30+ minute build the first time
- you want sovereignty over signing keys, perimeter rules, model catalog
- you're comfortable reading shell + understanding ZFS + secure-boot

No if:
- you want a pre-packaged ISO to download and dual-boot today (there isn't
  one — sovereign-os ships the **pipeline**, you build the image)
- you don't have or won't have SAIN-01-class hardware (you can still use
  this on lesser hardware but the AI workstation profile won't be useful)

---

## Prerequisites (build host — the machine that compiles the image)

You need a working Debian 13 / Ubuntu 24.04 (or compatible) machine with:

- **Root or sudo** (for `apt install` of the build toolchain)
- **GCC 14** (`apt install gcc-14 g++-14`)
- **64GB free disk** (kernel compile is hungry; tmpfs is even better)
- **mkosi** or **live-build** (the build picks; mkosi is default per SDD-003)
- **Python 3.11+** — install the test/lint deps with `make dev-deps` (pins one
  list, `requirements-dev.txt`: `pytest` + `pyyaml` + `jsonschema`)
- **Rust 1.89+** (edition 2024) for the `crates/` intelligence layer. Debian
  stable ships 1.85 — install the pinned toolchain via rustup with
  `scripts/install/rust-toolchain.sh` (user-level `~/.cargo`/`~/.rustup`, never
  apt; also run by `make provision`). Not needed for an image-only build.
- **Network access** to deb.debian.org + huggingface.co (post-install model pulls)

You can RUN sovereign-os on the **target hardware** (SAIN-01 or a profile).
You BUILD sovereign-os on any sufficient Debian-derivative.

---

## First commands (in order)

```sh
# 1. Clone
git clone https://github.com/cyberpunk042/sovereign-os
cd sovereign-os

# 2. Run the onboarding wrapper — walks you through 5 decisions
#    (profile · substrate · secure-boot posture · encryption · whitelabel),
#    sets up the dev environment, runs preflight.
scripts/onboard.sh

# 2b. (optional) Prefer to point-and-click the choices? Launch the build
#     configurator dashboard — pick profile / kernel / modules / CPU features /
#     packages / prepackaged tools (Claude Code, OpenCode, …) and it GENERATES
#     the exact `orchestrate.sh` command + overlay.yaml + operator-deps.toml.
#     Read-only, loopback-bound; it never builds anything itself.
python3 scripts/operator/build-configurator-api.py   # then open http://127.0.0.1:8100/

# 3. Validate the build plan without running anything
SOVEREIGN_OS_PROFILE=sain-01 scripts/build/orchestrate.sh run --dry-run

# 4. When you're ready to build for real (this takes 30+ minutes the first time
#    on SAIN-01-class hardware; needs sudo for apt + kernel compile)
SOURCE_DATE_EPOCH=$(date +%s) \
DEBIAN_SNAPSHOT=20260515T000000Z \
SOVEREIGN_OS_PROFILE=sain-01 \
  sudo scripts/build/orchestrate.sh run

# 5. Verify the build is reproducible (no operator-specific signatures)
sovereign-osctl audit provenance --deep build/sain-01/output/build-provenance.json

# 6. Write the image to your target disk (safety-gated; never touches running root)
sovereign-osctl install image --plan build/sain-01/output/sain-01.raw --to /dev/nvme1n1
SOVEREIGN_OS_CONFIRM_DESTROY=YES \
  sudo sovereign-osctl install image build/sain-01/output/sain-01.raw --to /dev/nvme1n1

# 7. Boot from that disk on the target hardware.
#    First boot runs the post-install assistant + applies hardening.

# 8. From the running sovereign-os system, day-to-day:
sovereign-osctl status                  # health overview
sovereign-osctl doctor                  # profile-conditioned sanity check
sovereign-osctl alerts                  # rule-derived alerts (no Alertmanager)
sovereign-osctl audit drift             # did my hardening config drift?
sovereign-osctl maintenance scrub       # on-demand ZFS scrub
```

If a step fails:
```sh
scripts/build/orchestrate.sh recover    # diagnoses the failure, offers 4 next actions
sovereign-osctl journal errors          # every warn/error across log files
```

---

## Where to read next

| If you want to… | Read |
|---|---|
| **Use the box from VS Code / Claude Code** (the local model over the Anthropic + OpenAI APIs) | [`docs/src/ai-backend.md`](docs/src/ai-backend.md) |
| Deliberate reasoning (CoAT), the Brain observatory, Background Tasks, the Code Console | [`docs/src/reasoning-operability.md`](docs/src/reasoning-operability.md) |
| Understand WHAT you're building (the Trinity, SAIN-01 hardware spec, runtime profiles) | [`docs/src/sain-01-master-spec.md`](docs/src/sain-01-master-spec.md) |
| Walk through the FULL lifecycle from clone → daily-use → decommission | [`docs/src/operator-journey.md`](docs/src/operator-journey.md) |
| End-to-end step-by-step install for your specific profile | [`docs/src/install-runbook.md`](docs/src/install-runbook.md) + [`docs/src/profiles/`](docs/src/profiles/) |
| What all the `sovereign-osctl` verbs do | [`docs/src/ops/manage.md`](docs/src/ops/manage.md) |
| The 26 design decisions that locked the architecture | [`docs/sdd/INDEX.md`](docs/sdd/INDEX.md) |
| The audit trail (every D-NNN decision) | [`docs/decisions.md`](docs/decisions.md) |
| The 18 real bugs caught + 5 distilled learnings | [`docs/src/tdd/bugs-caught.md`](docs/src/tdd/bugs-caught.md) |

---

## What sovereign-os is NOT

- **NOT a distro you download as an ISO**. It's the pipeline you USE to produce
  your own bootable image.
- **NOT a substitute for Tetragon or selfdef**. Those run ON the OS;
  sovereign-os builds the OS that runs them.
- **NOT a hosted service or SaaS**. Everything is local-default; no telemetry
  leaves your machine without explicit operator action.

---

## What this repo IS for (operator quality bar, verbatim, sacrosanct)

> "Do not rush anything and do not minimize anything nor should you
> compress or conflate or hallucinate anything"

> "I want things observable and operable and customizable, at all stages
> of lifecycle"

> "we always deliver IaC, high quality scripts and libs and configuration
> and easily tweakable and configurable and customisation and even via
> env vars when needed, or other pre-existing config or temporary file
> detected and restarting from there"

> "we remember the SFIF, Skaffold, Fundation, Infrastructure, Features"

> "I think Debian is a bit like saying we have our Arc but we start from
> there"

Every PR in this repo is reviewed against these.

---

## The four-repo ecosystem

| Repo | Role |
|---|---|
| **`cyberpunk042/sovereign-os`** (this) | BUILDS the OS — image generation + customization + lifecycle tools |
| [`cyberpunk042/selfdef`](https://github.com/cyberpunk042/selfdef) | RUNS on the OS — security daemon (Tetragon + agent-guard + notifier channels) |
| [`cyberpunk042/devops-solutions-information-hub`](https://github.com/cyberpunk042/devops-solutions-information-hub) | SYNTHESIZES knowledge — wiki second-brain; SAIN-01 master spec lives here |
| `cyberpunk042/root-ghostproxy` | GOVERNS AI agents on the OS — endpoint-mode safety envelope (proxy half disabled; SDD-046) |

---

## License

AGPL-3.0-or-later. See [`LICENSE`](LICENSE).
