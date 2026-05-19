# Backward-sweep findings — 2026-05-19

Source: backward-pass review of `~/infohub/raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md` (18341 lines), operator standing direction: "go backward a bit since it redefines some of the things".

## Redefinitions identified

| # | concept | later definition (dump lines) | earlier definition (dump lines) | severity | affected milestones |
|---|---|---|---|---|---|
| 1 | Profiles — Memory lens → Authority gate | 17468-17488 | 8420-8440 | **breaking** | sovereign-os M016 M017 / selfdef MS010 (memory lens framing supplanted) — also affects MS040 (already catalogued under authority arc; verify no memory-lens leakage) |
| 2 | Core Law — 5-line → 6-line "CPU enforces" explicit | 18303-18308 | 15350-15355, 15789-15794 | **clarifying** | sovereign-os M005 M006 M009 M020 (citations to earlier 5-line variants must be promoted to canonical 6-line at 18299-18305) |
| 3 | Authority Levels 0..6 — new explicit ladder | 17255-17278 | implicit everywhere earlier | **additive** | sovereign-os M005 M007 M014 M017 (must layer in citation to 7-level FSM at 17255-17278) |
| 4 | Trust Rings 0..4 — new explicit topology | 17282-17300 | dispersed (no ring topology) | **additive** | sovereign-os M011 M014 M016 (must layer in citation to 5-ring topology at 17282-17300) |
| 5 | Scheduler — component → first-class policy layer per profile | 17916-18040 | 312, 677, 1325 | **breaking** | sovereign-os M005 M007 M009 (citations to component-level scheduler must be promoted to profile-policy scheduler at 17916-18040 + 18001-18030) |
| 6 | Commit Authority — deterministic substrate → evidence-based earned authority | 17389-17506 | 1527, 1858, 2139, 2155, 2319 | **breaking** | sovereign-os M006 M010 (must distinguish runtime-level speculative commit (token masking) from durable-commit-authority arc at 17389-17421 + 17501-17517) |

## Patch plan

- **Pass 1**: Add an "AVX++ canon update" note to each affected milestone's cross-references section citing the later definition + severity.
- **Pass 2**: For breaking redefinitions, add new requirements (additive, never delete) that pin the later definition as canonical and mark earlier R-rows as superseded-by reference.
- **Pass 3**: Update the typed-mirror crate documentation (MS007 8/8 SATURATED) for any contract changes.

Operator standing direction (verbatim, 2026-05-18): *"layered: new direction ON TOP OF prior direction — never discarded"* — patches are ADDITIVE; earlier R-rows are not deleted.

## Pending

- All 6 redefinitions enumerated; patch passes to be executed after the UX/dashboard catalog (operator's freshest /goal emphasis at 2026-05-19).
