# sovereign-os default GRUB theme

Monochrome placeholder theme — text-only, no proprietary asset deps.

## Expected runtime files

`theme.txt` is the entry point (GRUB reads it from
`/boot/grub/themes/sovereign/theme.txt`). It references the following
pixmaps which are SHIPPED EMPTY in this overlay (operator must drop
real PNGs to land a real visual; the monochrome fallback below works
without them):

| pixmap (referenced) | purpose | fallback |
|---|---|---|
| `background.png` | desktop image | absent → solid `desktop-color` (#0c0c12) |
| `select_*.png` (n,c,e,w,nw,ne,sw,se) | selected-item pixmap-style 8-tile | absent → solid `selected_item_color` background |
| `terminal_box_*.png` (8 tiles) | grub shell border | absent → no border |
| `scrollbar_*.png` (n,c,s) | scrollbar thumb 3-tile | absent → no scrollbar visual |

Operators wanting a real brand visual drop the matching PNGs alongside
`theme.txt` and re-render via `scripts/build/orchestrate.sh run` (or
`sovereign-osctl whitelabel apply` post-install).

Per SDD-012, brand promotion requires no render-engine code change —
it's a `whitelabel/<brand>/overlays/grub-theme/*.png` drop-in.

## Operator-verbatim motd surfacing

`theme.txt`'s bottom vbox carries the operator's sacrosanct motd line
("quality over quantity · honesty over cheats and lies") so it's
visible at every boot — fulfills the goal-text's "we will still see
it written somewhere" requirement at the highest-visibility surface
of the system (the boot menu).

Layer 3 test `tests/nspawn/test_whitelabel_overlays_present.sh`
gates that motd presence + boot-menu + progress-bar declarations.
