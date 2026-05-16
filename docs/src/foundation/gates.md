# Stage gates 1–5

Operator-review checkpoints between tiers.

| Gate | Trigger | What operator reviews | Status |
|---|---|---|---|
| **1** | PRs 1–3 merged | Structural foundation matches selfdef rhythm | ✅ fired |
| **2** | PR 4 merged | Substrate decision (Q-001 + Q-016) — primary: mkosi-on-Debian-13 | ✅ fired; **operator decision pending** |
| **3** | PR 6 + PR 5 merged | Profile schema lock-in (Q-002) — hybrid model substantively closed via merger | ✅ fired; **operator confirmation pending** |
| **4** | PR 8 merged | Whitelabel mechanism + legal scope (Q-004) — proposals in SDD-007 | ✅ fired; **operator decision pending** |
| **5** | PR 10 merged | Foundation-complete — authorizes Stage 2 | ✅ fired |

Substantive Stage-2 work has already started landing on main per operator directive ("WHEN ITS IN THE GOAL YOU PROCEED").

## Open operator decisions

These are the items waiting on operator decision before Stage-2 work can fully lock:

1. **Q-001 + Q-016** — confirm `mkosi-on-Debian-13` as the substrate (recommended) OR pick an alternative.
2. **Q-002** — confirm `single-parent + mixins` hybrid (substantively validated; needs sign-off).
3. **Q-003** — brand identity (deferrable past Q-004 closure).
4. **Q-004** — `dfsg-only` vs `trademark-cleared` vs `internal-only` legal scope.
5. **Q-017** — confirm direct-stack inference architecture (SDD-011).
