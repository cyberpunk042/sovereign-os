# Whitelabel mechanism (PR 8 / SDD-007)

Substrate-agnostic 2-layer architecture per [`docs/sdd/007-whitelabel-mechanism.md`](https://github.com/cyberpunk042/sovereign-os/blob/main/docs/sdd/007-whitelabel-mechanism.md).

## Architecture

```
profiles/<id>.yaml  ──whitelabel: profile─▶  whitelabel/<id>.yaml
                                                       │
                                                       ▼
                                          scripts/whitelabel/render.py  (Layer 1)
                                          (substrate-agnostic file-tree changeset)
                                                       │
                                                       ▼
                                          substrate adapter  (Layer 2)
                                          (mkosi / live-build / rpm-ostree / NixOS)
                                                       │
                                                       ▼
                                          pre-build patches + during-install
                                          substitutions + post-install scripts
```

## 7 strategies

| Strategy | When | Swap-without-rebuild? |
|---|---|---|
| `template-substitution` | pre-build | **Yes** (re-render + copy) |
| `file-overlay` | pre-build | **Yes** (asset replacement) |
| `package-replacement` | pre-build | Partial (alternatives switch) |
| `build-time-flag` | pre-build (compile) | **No** (kernel rebuild required) |
| `install-time-substitution` | during-install | **No** (one-shot) |
| `first-boot-script` | post-install | One-shot; re-runnable via maintenance hook |
| `must-not-touch` | validation | Refused — cannot override legal floor |

## Default whitelabel — placeholder pending Q-003

Current `whitelabel/default.yaml` uses neutral "Sovereign OS" naming + GitHub URLs. Operator commits real brand identity (name, palette, logo SVG/PNG) at a future PR; templates re-render automatically via `sovereign-osctl whitelabel apply default`.

## Q-004 — legal scope

Operator picks at Gate 4:

- **A. `trademark-cleared`** (public-distribution) — `LICENSE-DEBIAN-HERITAGE.md` ships; redistributable.
- **B. `internal-only`** — Personal workstation; lower bar; NOT redistributable.
- **Default**: `dfsg-only` (legal floor strict; upgrade-path to A by changing one field).

## On-running-system apply

```sh
sovereign-osctl whitelabel apply <id>
```

Renders to `/tmp/sovereign-os-whitelabel-<id>/`. Non-rebuild strategies (template-substitution, file-overlay) can be copied to live system; build-time-flag strategies require rebuild.
