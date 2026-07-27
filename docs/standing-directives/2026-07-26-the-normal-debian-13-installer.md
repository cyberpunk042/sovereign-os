# Standing directive — the installer IS the normal Debian 13 installer (d-i), not a bespoke TUI

**Status**: ACTIVE (operator directive, 2026-07-26, verbatim — logged during the work)
**Audience**: every session touching `SOVEREIGN_OS_ARTIFACT=installer`, SDD-013,
`scripts/build/installer-cdd/*`, `scripts/install/installer-tui.sh`, the build panel
**Supersedes**: the "live-build ISO + guided TUI" delivery in
[2026-07-25-installer-onto-nvme.md](2026-07-25-installer-onto-nvme.md) §2(b) and in
SDD-013. Everything else in that directive stands.

## Verbatim operator statements (sacrosanct — do not paraphrase)

On booting the live-build ISO and finding the whiptail TUI instead of a Debian install:

> "it was a weird launcher rather than the standard ubuntu 13 insaller, weird first bug..and then it got stuck at the start of sovereign-is installer..."

The requirement, stated plainly:

> "it should be the normal debian 13 installer..."

On being asked whether this meant a different path:

> "a different path ? the right path you mean.. the current installr is crap"

On being handed the TUI ISO a second time:

> "same mother fucking crap.. this is not the debian 13 installer at all wtf is this trash... I wasted my time again"

## What this directive establishes

1. **`SOVEREIGN_OS_ARTIFACT=installer` means debian-installer.** It maps to the
   `installer-cdd` substrate (simple-cdd → debian-cd → a real d-i ISO), NOT to
   live-build. An operator booting the installer USB gets the standard Debian 13
   install experience: the normal partitioner, the normal prompts, offline from the
   CD's own mirror.
2. **The bespoke TUI is not the installer.** `scripts/install/installer-tui.sh`
   remains as the reflash driver on an already-sovereign machine; it is not what
   `ARTIFACT=installer` produces, and it must never again be what the operator is
   handed when they ask for an installer.
3. **"Standard" is a hard requirement, not a preference.** The failure that produced
   this directive was not that the TUI was broken — it was that it existed at all
   where a Debian installer was expected. A replacement that is bespoke-but-working
   does not satisfy this directive.

## Why it took two rounds (recorded so it is not repeated)

The first fix repointed step 07 only. Steps 05 and 06 still rejected the new
substrate, and step 07 sourced a STALE env handoff from step 05 — so the pipeline
reported `substrate=installer-cdd` at step 05 and silently ran `live-build` at step
07, left an hour-old ISO in place, and exited 0. The operator flashed the same TUI
image twice. Adding a substrate touches every stage that dispatches on it;
`tests/lint/test_every_substrate_is_handled_end_to_end.py` now enforces that.
