# sovereign-os panel design grammar

Operator-named requirement (2026-06-12, verbatim intent): primary actions
"should have been much clearer and easy to find without a doubt … why
isn't the button colored … think of this at scale." This file is the
at-scale answer: every panel follows the same visual grammar so an
operator landing on ANY of the ~37 panels finds the action surface
without reading.

## Tokens (every panel reuses these names)

```css
--bg --fg --muted --border
--accent   /* brand / primary path      (#9bd1ff default) */
--good     /* green — healthy, safe-run  (#7ad17a) */
--warn     /* amber — heavy, attention   (#e6c062) */
--bad      /* red   — destructive, error (#ff7676) */
```

### Scale (SDD-145 — declared in the synced app-shell `:root`, reach all panels)

Grounded on the fleet's dominant literals. `--fs-*`/`--space-*` are **rem** so they
auto-compose with the personalization `--font-scale` zoom (the html root is
`calc(14px * var(--font-scale))`) — **never** wrap them in `calc(*--font-scale)`.

```css
/* type */    --fs-2xs:.7  --fs-xs:.72 --fs-sm:.78 --fs-base:.85 --fs-md:1 --fs-lg:1.4  (rem)
/* radius */  --radius-xs:2 --radius-sm:3 --radius-md:4 --radius-lg:6 (px) · --radius-pill:999px
/* space */   --space-2xs:.2 --space-xs:.3 --space-sm:.4 --space-md:.6 --space-lg:.9 --space-xl:1 --space-2xl:1.2 --space-3xl:1.6  (rem)
```

Prefer `var(--fs-*)` / `var(--radius-*)` / `var(--space-*)` over raw literals; genuine
one-offs (and the `@media print` `pt` sheet + `50%` circles) stay literal. build-configurator
is the reference adopter.

## Button hierarchy — THE rule

| Class | Look | Use for | Per view |
|---|---|---|---|
| `.btn` | ghost (border only) | chrome: copy, fold, nav, tour | any |
| `.btn.action.primary` | **filled accent** | the view's main path | **max ONE** |
| `.btn.action.go` | **filled green** | safe executable step | few |
| `.btn.action.heavy` | **filled amber** | long/expensive/root-gated, confirm-first | few |

Hard rules:
1. An executable action is NEVER a ghost button. Ghost = chrome only.
2. One `.primary` per view. If everything is primary, nothing is.
3. `.heavy` actions confirm before running and state their cost in the
   label (e.g. `▶ BUILD image (~30 min)`).
4. Disabled = `opacity:.35` + `cursor:not-allowed`, never hidden —
   visible-but-disabled teaches what the page can do.

## Execution surfaces

Anything that executes server-side lives in a **console card**: left
accent bar (`--good`), tinted background, a status dot (`.run-dot`,
pulsing amber while busy), the action row, then the live log `<pre>`.
The card heading states the trust contract verbatim:
*"executes on the server — the exception to ⚡ YOU RUN"*.

## Status pills

`live ✓` (green) / `live ✗` (red) / snapshot (muted) — a panel must say
which data source it is on. Baked-snapshot fallback is fine; pretending
to be live is not.

## Reference implementation

`webapp/build-configurator/index.html` (Run console + topbar target
toggle). When touching any other panel, converge it to this grammar
rather than inventing a new one.
