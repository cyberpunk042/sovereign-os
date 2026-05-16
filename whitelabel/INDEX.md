# Whitelabel index

Catalog of declared whitelabel definitions. Each whitelabel MUST
validate against [`../schemas/whitelabel.schema.yaml`](../schemas/whitelabel.schema.yaml).
See [`../docs/sdd/007-whitelabel-mechanism.md`](../docs/sdd/007-whitelabel-mechanism.md)
for the mechanism design.

## Active whitelabels

| id | name | status | compliance | maintainer | notes |
|---|---|---|---|---|---|
| [`default`](default.yaml) | Sovereign OS Default Whitelabel | draft | dfsg-only | cyberpunk042 | Placeholder pending Q-003 brand-identity commit |

## Reserved slots (future whitelabels operator may want)

| id | reserved for | When |
|---|---|---|
| `internal` | Personal sovereign workstation; lower legal bar | When Q-004 closes to "internal-only" path |
| `public` | Trademark-cleared public distribution | When Q-004 closes to "trademark-cleared" path + brand identity committed |
| `productX` | Future commercial productization (placeholder) | If/when operator pursues commercial product line |

## Per-surface strategy taxonomy

Per SDD-007's 7 strategies:

| Strategy | When applied | Swap-without-rebuild? |
|---|---|---|
| `template-substitution` | pre-build | Yes (most) |
| `file-overlay` | pre-build | Yes |
| `package-replacement` | pre-build | Partial |
| `build-time-flag` | pre-build (compile) | No |
| `install-time-substitution` | during-install | No (already installed) |
| `first-boot-script` | post-install | No (one-shot; re-runnable as maintenance hook) |
| `must-not-touch` (legal floor) | validation | n/a — refused at validation |

## Legal-floor (enforced)

The validator rejects any whitelabel `surfaces:` entry targeting:

- `/etc/debian_version` (provenance)
- `/usr/share/doc/*/copyright` (license attribution; matches glob)
- `/usr/share/man/*` (upstream manpages)
- `*/debian-logo*` (trademark)
- `*/debian-swirl*` (trademark)

Source: SDD-006 § "Legal floor"; SDD-007 § "Strategy 7 — must-not-touch".

## Future additions to this directory

When a whitelabel ships substantive content beyond the YAML
declaration, the directory grows:

```
whitelabel/
├── INDEX.md                   (this file)
├── default.yaml               (declarations)
├── default/                   (per-whitelabel asset tree; lands at Stage 2+)
│   ├── templates/
│   │   ├── os-release.tmpl
│   │   ├── installer-welcome.tmpl
│   │   └── ...
│   ├── overlays/
│   │   ├── plymouth-theme/
│   │   ├── grub-theme/
│   │   └── ...
│   └── scripts/
│       └── first-boot-greeting.sh
├── internal.yaml              (if operator picks internal-only path)
├── public.yaml                (if operator picks public-distribution path)
└── productX.yaml              (future)
```

This PR (PR 8) ships only the YAML declarations and INDEX; template /
overlay / script bodies land at Stage 2+ alongside the render engine +
substrate adapter.
