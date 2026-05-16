# SDD-012 — Brand identity placeholder strategy (Q-003 deferred-with-criteria)

> Status: **review**
> Owner: cyberpunk042
> Last updated: 2026-05-16
> Closes findings: Q-003 (deferred-with-criteria, not closed-as-decided)
> Derived from: SDD-007 (whitelabel mechanism), info-hub directive
> `raw/notes/2026-05-16-user-directive-sovereign-os-arc-opening-limit-continuation.md`

## Problem

Q-003 ("Whitelabel brand identity: name · palette · logo") is open and
deliberately deferrable past PR 8 (per `docs/decisions.md` decisions
table). The operator's focus is technical sovereignty, not branding.

But "deferred" cannot mean "broken" — every rendered image must still
ship a coherent identity. Today `whitelabel/default.yaml` carries
placeholder values that the render engine substitutes into `/etc/issue`,
`/etc/os-release`, etc.

This SDD specifies the **placeholder contract**: what stays
placeholder, what is operator-fixed, when a "real" brand becomes
mandatory, and how to detect placeholder leaks into production builds.

## The placeholder contract (current state, intentional)

`whitelabel/default.yaml` is the default + active whitelabel. It uses:

| Field | Placeholder value | Why placeholder |
|---|---|---|
| `branding.os_name` | `"Sovereign OS"` | working name; operator may rename |
| `branding.os_pretty_name` | `"Sovereign OS v0.1 (Foundation Phase)"` | versioned; reflects current phase |
| `branding.os_id` | `sovereign` | machine-readable; stable for as long as the codename holds |
| `branding.os_codename` | `trinity` | references SRP Trinity; can stay |
| `branding.vendor` | `cyberpunk042` | operator handle; not corporate |
| `branding.home_url` | `https://github.com/cyberpunk042/sovereign-os` | github repo until something better exists |
| `branding.palette.*` | monochrome | no aesthetic commitment |
| `branding.logo_*` | unset | no logo asset committed |

## The legal-floor contract (unchanged by Q-003 resolution)

Regardless of how Q-003 resolves, **the following remain untouchable**
(per SDD-006 surface audit + SDD-007 whitelabel mechanism):

- `/etc/debian_version` — present + unmodified
- `/usr/share/doc/*/copyright` — present + unmodified
- `/usr/share/man/*` — present + unmodified
- `debian-logo*.{svg,png}` — present + unmodified

The render engine `scripts/whitelabel/render.py` enforces this via
`violates_legal_floor()` + the `must-not-touch` strategy entries in
`schemas/whitelabel.schema.yaml`.

In `/etc/os-release` specifically, the legal contract is:
- `ID_LIKE=debian` — preserved (so downstream tools recognize this as
  a Debian derivative)
- `VERSION_CODENAME` may differ from Debian's codename (operator-chosen)
- `NAME`/`PRETTY_NAME`/`ID` may diverge (operator-chosen)

Layer-3 test `tests/nspawn/test_whitelabel_render_to_disk.sh` +
`test_whitelabel_render_live_build.sh` gate this contract.

## Promotion criteria — when a "real" brand becomes mandatory

A real brand identity (palette + logo + final name) is REQUIRED before:
1. The operator decides to **publicly distribute** a sovereign-os image
   (Q-004 resolution dependent — see decisions log).
2. A **second public-facing surface** is added that needs a logo
   (boot splash, login screen, GRUB theme, plymouth) — currently
   placeholders are uniform monochrome, which is shippable but austere.
3. The operator names the project something other than "sovereign-os".

Until any of those, the placeholder stays.

## Promotion mechanism — how a real brand lands

When the operator promotes a brand, they:

1. Create `whitelabel/<brand>/` with the same shape as
   `whitelabel/default/` (templates/, overlays/).
2. Create `whitelabel/<brand>.yaml` with the new `branding:` block.
3. Set `/etc/sovereign-os/active-whitelabel` (or pass
   `--whitelabel whitelabel/<brand>.yaml` to the render engine).
4. Rebuild + re-render via `scripts/build/orchestrate.sh run`.

No render-engine code change is required — the engine is whitelabel-agnostic
by design (SDD-007). New brands ship as data, not code.

## Placeholder-leak detection

Layer 3 test `test_whitelabel_render_live_build.sh` (added 2026-05-16)
includes a placeholder-leak gate: after render, no active-content
line in the rendered chroot may contain `${var}` sigils. If any
template variable goes unsubstituted, the test fails — meaning the
operator's branding YAML must declare every variable the templates
reference, or no image ships.

This is the executable proof of P4 (Declarations Aspirational Until
Verified) applied to brand identity.

## Goals

1. **Deferral made coherent** — no broken image while Q-003 stays open.
2. **Legal floor preserved** — every image carries the must-not-touch
   set; verified by Layer 3.
3. **No code change required for promotion** — a future brand lands
   as a `whitelabel/<id>/` directory + `whitelabel/<id>.yaml`, not as
   a render-engine patch.
4. **Placeholder leaks detected automatically** — CI fails if a
   template variable goes unsubstituted.

## Non-goals (this SDD)

- Does NOT decide the eventual brand name (operator-driven).
- Does NOT decide the eventual palette or logo (operator-driven; can
  be commissioned or DIY).
- Does NOT prescribe a license model for distributed images
  (Q-004 covers that).

## Cross-references

- SDD-006 (surface audit — what must-not-touch protects)
- SDD-007 (whitelabel mechanism — the 7-strategy engine)
- `whitelabel/default.yaml` + `whitelabel/default/`
- `scripts/whitelabel/render.py` § `violates_legal_floor`
- `tests/nspawn/test_whitelabel_render_to_disk.sh` (mkosi substrate test)
- `tests/nspawn/test_whitelabel_render_live_build.sh` (live-build + placeholder-leak gate)
