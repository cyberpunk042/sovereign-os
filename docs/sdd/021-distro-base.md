# SDD-021 — Distro-base (Q-016 resolution)

> Status: **review**
> Owner: cyberpunk042
> Last updated: 2026-05-16
> Closes findings: Q-016 (distro-base reconsideration: "Debian-as-Ark")
> Derived from: SDD-003 (substrate survey), SDD-018 (kernel choice),
> the operator's verbatim "Debian as Ark" framing.

## Problem

Q-016 ("Distro-base reconsideration: Debian-as-Ark") has been open
since PR 1. The operator's framing was metaphorical — "Debian is a
bit like saying we have our Arc but we start from there, kind of
thing" (verbatim) — meaning Debian is the foundation, not the
destination, and we're free to reconsider it later if needed.

SDD-003 (substrate survey) implicitly resolved Q-016 by picking
**mkosi-on-Debian-13** as the foundation-phase substrate. This SDD
makes that resolution explicit.

## Decision: **Debian 13 (trixie) is the foundation distro-base, intentionally**

Foundation phase commits to Debian 13 (trixie) as the build base for
all profiles (sain-01, old-workstation, minimal, developer). Whether
to reconsider in a future phase is operator-driven; this SDD specifies
the **criteria** for reconsideration.

## Why Debian 13 (already implied by SDD-003)

1. **Stable + long-lived** — predictable security-update cadence;
   matches the operator's "we do things properly" bar.
2. **mkosi-native** — substrate of choice supports it as a first-class
   target (`Distribution=debian Release=trixie` is the working line
   in `mkosi.conf`).
3. **systemd-only** — sovereign-os's lifecycle relies on systemd
   units (sovereign-firstboot.target, sovereign-tetragon-verify.timer,
   etc.). Debian + systemd is the well-tested combo.
4. **AGPL-3.0+-compatible package ecosystem** — sovereign-os ships
   under AGPL-3.0-or-later (per D-001); Debian's licensing posture
   is rigorously curated.
5. **Operator-familiar** — selfdef + info-hub both Debian-derived.
   Cross-repo cognitive load stays low.

## Reconsideration criteria — when to revisit

Q-016 stays openable-on-demand. A future SDD would re-open it if any
of the following materializes:

1. **Debian deprecates a load-bearing feature** (e.g., drops AVX-512
   support in the default kernel) and the workaround is harder than
   migrating.
2. **Operator wants atomic-OS semantics** (rpm-ostree / NixOS) and the
   inference stack tolerates the rebuild-vs-mutable tradeoff.
3. **Hardware-driver gap** that's faster to resolve via Fedora / SUSE
   kernel-team backports than waiting for Debian's pace.
4. **Sovereignty pressure** that requires forking Debian itself.

None of these are present in the foundation phase. The recommendation
in SDD-003 stands: stay on Debian 13.

## What "Debian as Ark" means operationally

The operator's framing:
> "Debian is a bit like saying we have our Arc but we start from
> there, kind of thing"

Operational reading:
- **Ark** = the foundation we sail on, not the destination
- **From there** = sovereign-os builds atop Debian without inheriting
  Debian's posture (sovereign-os adds Tetragon perimeter; bans
  popularity-contest / apport / whoopsie / snapd / ubuntu-advantage-
  tools; replaces apt-default kernel for sain-01; whitelabels every
  surface that legal-floor allows)
- **Kind of thing** = the metaphor is loose enough that the operator
  reserves the right to swap the Ark later

This SDD honors the metaphor by locking the **current Ark** while
keeping the **departure terms** explicit.

## Cross-references

- SDD-003 (substrate survey — picked mkosi-on-Debian-13)
- SDD-006 (Debian surface audit — what we touch + what we don't)
- SDD-007 (whitelabel — how we depart visually + textually)
- SDD-015 (secure-boot — operator-owned chain on top of Debian's
  default-shim path)
- SDD-018 (kernel — sain-01 builds its own; others use Debian's)
- SDD-019 (reproducibility — Debian snapshot.debian.org is the
  reproducibility anchor)
- D-001 (license: AGPL-3.0+-or-later)
- Operator verbatim (sacrosanct): `raw/notes/2026-05-16-user-directive
  -sovereign-os-arc-opening-limit-continuation.md` in info-hub —
  "Debian is a bit like saying we have our Arc but we start from
  there, kind of thing"
