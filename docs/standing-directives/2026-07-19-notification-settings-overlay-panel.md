# Standing directive — shared notification-settings overlay panel + trigger markdown properties

**Status**: ACTIVE (operator directive, 2026-07-19, verbatim — logged BEFORE acting)
**Audience**: every Claude Code session working this feature
**Extends**: [2026-07-19-notification-wiki-operability-mode.md](2026-07-19-notification-wiki-operability-mode.md) (notifykit + wikiops, merged PR #248)

## Verbatim operator statement (sacrosanct — do not paraphrase)

> "we are also going to need a shared overlay panel for the configuration of
> the notifications, from the settings pane on the top-right in the header.
> The whole settings range, I can also chose for the trigger to be
> important:true and such markdown properties & metadata as much has in the
> header."

## Reading (agent working notes — the verbatim above governs)

1. A **shared overlay panel** — one component shared across the cockpit
   panels — for **configuring the notifications**.
2. Opened **"from the settings pane on the top-right in the header"** — the
   shared header's settings surface.
3. **"The whole settings range"** — the full notifykit surface: channels
   on/off, per-channel gates (min_priority × min_urgency), static pins,
   global default override.
4. **Triggers carry markdown-frontmatter-style properties & metadata** —
   *"I can also chose for the trigger to be important:true and such markdown
   properties & metadata as much has in the header"* — i.e. the same
   key:value property shape markdown headers (frontmatter) carry, applied to
   notification triggers (e.g. `important: true`).
