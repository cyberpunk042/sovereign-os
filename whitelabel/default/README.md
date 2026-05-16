# whitelabel/default/ — content for the default whitelabel

Bodies consumed by `scripts/whitelabel/render.py` per SDD-007.

## templates/ (template-substitution strategy)

| File | Renders to | Strategy |
|---|---|---|
| `os-release.tmpl` | `/etc/os-release` + `/usr/lib/os-release` | template-substitution |
| `issue.tmpl` | `/etc/issue` | template-substitution |
| `motd.tmpl` | `/etc/motd` (static; first-boot-greeting.sh handles dynamic motd) | template-substitution |
| `dpkg-origins-sovereign.tmpl` | `/etc/dpkg/origins/sovereign` | template-substitution |
| `installer-welcome.tmpl` | installer banner (Q-008-conditional) | install-time-substitution |

Variables substituted from `whitelabel/default.yaml` `branding:` block (`${os_id}`, `${os_pretty_name}`, `${home_url}`, `${motd}`, etc.).

## overlays/ (file-overlay strategy)

| Directory | Renders to | Strategy |
|---|---|---|
| `plymouth-theme/` | `/usr/share/plymouth/themes/sovereign/` | file-overlay |
| `grub-theme/` | `/boot/grub/themes/sovereign/` | file-overlay |

Each overlay is a directory tree; the render engine copies the tree into the substrate's `mkosi.extra/` (or `includes.chroot/` for live-build) preserving structure.

## scripts/ (first-boot-script strategy)

Empty by default — the operator-verbatim greeting lives in `scripts/whitelabel/first-boot-greeting.sh` at the repo root (referenced from `whitelabel/default.yaml`).

## Status: placeholder pending Q-003

These template + overlay bodies use neutral "Sovereign OS" branding + GitHub URLs. When operator commits brand identity (name + palette + logo SVG/PNG), update:

- `whitelabel/default.yaml` `branding:` block (variables)
- `overlays/plymouth-theme/` (real script + logo PNG + spinner frames)
- `overlays/grub-theme/` (background PNG + terminal box assets)

The template files (`*.tmpl`) only need re-rendering after `branding:` edits — that happens automatically via `sovereign-osctl whitelabel apply default`.

## Legal floor (enforced by render.py)

These templates never touch:

- `/etc/debian_version` (Debian provenance retained)
- `/usr/share/doc/*/copyright` (GPL/AGPL/MIT attribution)
- `/usr/share/man/*` (upstream manpages)
- `*/debian-logo*`, `*/debian-swirl*` (Debian trademark assets)

The render engine refuses overlays that match these patterns. See SDD-006 § Legal floor.
