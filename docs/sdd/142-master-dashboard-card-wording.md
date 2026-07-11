# SDD-142 — Phase 4: master-dashboard section-card SB-077 clause consistency

> Status: draft
> Owner: operator-directed; agent-authored
> Last updated: 2026-07-11
> Closes findings: the empty-state wording theme's last piece (SDD-140 daemon-unreachable cards + SDD-141 data-source banners). The master-dashboard front door's three section scaffolds carried an SB-077 reference but in three different phrasings: `route table unreachable — populates when /routes + /health are reachable (nothing fabricated, SB-077)`, `collision check unavailable — /collisions unreachable (SB-077)`, `selfdef discovery unavailable — /discover unreachable (SB-077)`. Recover band (SDD-142 / E11.M142 per SDD-100).
> Derived from / extends: SDD-140/141 (empty-state wording convergence); SDD-133 (master-dashboard resilience — owns these scaffolds). §1g / SB-077.

## Mission

Normalize the three master-dashboard section scaffolds to the canonical honesty clause `Nothing is fabricated (SB-077).` so the front door's empty states read uniformly with the rest of the cockpit — completing the empty-state wording consistency theme.

## Grounded design (visible-copy only, 1 panel + 1 lint assertion)

- `route table unreachable — populates when /routes + /health are reachable **(nothing fabricated, SB-077)**` → `… reachable. **Nothing is fabricated (SB-077).**`
- `collision check unavailable — /collisions unreachable **(SB-077)**` → `… unreachable. **Nothing is fabricated (SB-077).**`
- `selfdef discovery unavailable — /discover unreachable **(SB-077)**` → `… unreachable. **Nothing is fabricated (SB-077).**`

The leading phrases (`route table unreachable`, `collision check unavailable`, `selfdef discovery unavailable`) — pinned by `test_master_dashboard_resilience.py` — are untouched, so only the honesty tail changes and the resilience lint stays green.

## R10212 / SB-077 preserved

Visible-copy only. No behaviour/data/runtime change; the SB-077 honesty reference is preserved (now uniform). R10212 untouched.

## Verification

- `tests/lint/test_master_dashboard_resilience.py` extended: NEW `test_offline_scaffolds_carry_the_canonical_sb077_clause` asserts each of the 3 scaffolds carries `Nothing is fabricated (SB-077).`; the existing leading-phrase + allSettled + initial-paint assertions still pass.
- Full `make test` green (`test_master_dashboard_demo_richness.py` + the demo/resilience lints unaffected — the leads are unchanged).

## On completion — empty-state wording theme COMPLETE

Every cockpit empty state now reads uniformly: daemon-unreachable cards (SDD-140), data-source banners (SDD-141), and the front-door section scaffolds (this SDD) all use the canonical `Nothing is fabricated (SB-077).` honesty clause. **Recommended next stream is substantive, not cosmetic:** either the ux-audit **option B** (add genuine `next:`/`Run:` next-step hints to the 5 modules that score 5/6, raising them to 6/6 + regenerating the SDD-139 baseline — real CLI ergonomics; the bashrc `--apply`/`--confirm` dry-run gate is a separate operator-greenlit SDD), or an **SDD-040 evolution round** to reconcile the `--good/--bad` vs `--ok/--danger` token vocabularies (unblocks a real spacing/typography scale).

## Cross-references

- SDD-140 (daemon-card wording); SDD-141 (banner wording); SDD-133 (`test_master_dashboard_resilience.py`, which owns these scaffolds); `webapp/master-dashboard/index.html`. SDD-100 — band scheme.
