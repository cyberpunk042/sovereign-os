# SDD-996 — SDD INDEX status completeness: merged SDDs are marked `complete`, enforced by a lint (F-2026-099)

> Status: draft
> Owner: operator-directed 2026-07-14 (phase-1 audit continuation, "continue" → "merged → complete"); agent-authored.
> Closes: **F-2026-099** (LOW) — the draft→complete half of INDEX status hygiene.
> Mandate module: **E11.M996**.
> Number band: **950–999 (phase-1 audit session)** per SDD-100.

## The gap

SDD-961 (F-2026-031) gave the SDD INDEX status *hygiene* — a valid status
vocabulary + a lint blocking stale feature-branch references. It did **not**
enforce the `draft → complete` transition. The audit's residual: of 178 rows,
**only 2 were `complete`**, while **44** declared in their own Notes that the work
had **shipped on branch / this session** — i.e. merged to `main` (a row is only on
`main` because its PR merged). A shipped SDD frozen at `draft` makes the index lie
about what is done.

Operator directive 2026-07-14: **"merged → complete"** — mark every SDD whose PR
merged as `complete`, leave genuinely in-flight ones `draft`, derive "merged" from
git history + the INDEX's own "shipped on branch" notes, and add a lint so a
shipped SDD can't sit stale as draft.

## The change — evidence-based flip + a recurrence lint

**Data (this pass): 42 rows `draft → complete`.** The flip set is exactly the draft
rows whose Notes carry a **clean shipped-marker** (`shipped on branch` /
`shipped this session` / `✓ shipped`) with **no caveat**. That is the reliable
in-band "merged" signal the operator named — the author's own declaration that the
work landed, and the row is on `main` because the PR merged.

**Deliberately NOT flipped** (marking these `complete` would overstate status):

- **3 caveated shipped rows** stay `draft`: SDD-984 / SDD-985 (decision-packages
  *awaiting an operator decision*) and SDD-146 (stacked on another PR; its
  "open PR" note is stale but the row is uncertain — left for operator eyes).
- **76 older rows carry no shipped claim at all** (the foundation band 046–071 /
  101–126 and others predating the "shipped on branch" convention). They are on
  `main`, but their rows assert no completion, and inferring `complete` for 76 rows
  without in-band evidence would be fabricating status — several may be
  design / superseded / scoping docs, not shippable implementations. Left untouched;
  a per-row classification pass (with operator eyes) is the honest way to close them.
- **The deliberate non-draft statuses are untouched**: 40 `review`, 4 `active`
  (e.g. SDD-993, the GPU-topology anchor whose doc shipped but whose reconcile arc
  is live), 4 `accepted`, 1 `scoping`.

Result: **44 `complete`** (was 2), 84 `draft`, 40 `review`, 4 `active`, 4 `accepted`,
1 `scoping`, 1 `draft (decision pending)`.

**Lint (recurrence prevention): `tests/lint/test_sdd_index_status_completeness.py`.**
The enforceable rule is exactly the operator's concern — *a shipped SDD may never
sit at `draft`*: a row with a clean shipped-marker (no caveat) must have advanced
past `draft` (normally `complete`; a deliberate `active`/`review`/`accepted` for an
arc still in motion is also allowed). Caveated rows and rows with no shipped claim
are exempt. Plus a status-vocabulary guard and an anti-freeze floor (≥40 rows
`complete`).

## Verification (real, observed)

- The 42 flips applied by a scripted status-cell rewrite (only the matching rows'
  status field changed; titles/notes untouched). New distribution confirmed above.
- `python3 -m pytest tests/lint/test_sdd_index_status_completeness.py` → **3 passed**
  (the rule initially caught SDD-993 `active`+shipped — corrected: the rule targets
  `draft`, not "must be complete", so deliberate `active` anchors are allowed).
- Existing `test_sdd_index_hygiene` / `test_sdd_index_consistency` /
  `test_sdd_content_extended` / `test_sdd_reachability` → **28 passed** (the flip
  keeps the status vocabulary valid). `ruff` clean. Full `tests/lint` green.

## Scope / safety

`docs/sdd/INDEX.md` (42 status cells `draft→complete`) + a new `tests/lint/` file +
this SDD + registries. **No SDD content changed** — only status cells that already
declared shipped. No code, crate, runtime, or webapp change; no new dependency;
collision-safe. R10212 / MS043 untouched. MS003 `unsigned-pending-MS003`.

This SDD's own INDEX row lands `draft` (it is not merged yet); its Notes say
"shipping this session" (not the "shipped on branch" marker), so the new lint does
not require it to advance until it actually merges — the same honest lifecycle it
enforces for every other row.

## Non-goals

- Classifying the 76 no-shipped-claim foundation rows (needs per-row judgment —
  complete vs design vs superseded; an operator-eyes follow-up).
- Ratifying the 2 awaiting-decision decision-packages (SDD-984/985 — operator's call).
- Reconciling the SDD *doc-header* `Status:` fields with the INDEX column (separate;
  the audit item is the INDEX column).

## Cross-references

- `docs/sdd/INDEX.md` — the 42 flipped status cells
- `tests/lint/test_sdd_index_status_completeness.py` — the shipped⇒not-draft rule
- `tests/lint/test_sdd_index_hygiene.py` — SDD-961, the status *vocabulary* + branch-ref half this builds on
- `docs/review/phase-1/99-findings-ledger.md` — F-2026-099 (closed here); F-2026-031 (SDD-961, the hygiene half)
