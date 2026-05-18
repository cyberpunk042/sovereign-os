# SDD-037 — Verbatim-preservation doctrine (E10.M11 / R367)

> Status: **review**
> Owner: sovereign-os core
> Last updated: 2026-05-18
> Closes findings: E10.M11 (mandate decomposition)
> Derived from: /goal directive 2026-05-18 ("continue till you meet ALL
> MY REQUIREMENTS without MINIMIZING or rephrasing or compressing or
> conflating") + the lived practice of R355-R366 (12 rounds covering
> 20+ master spec sections + dump-tail + macro-arc plan refinements)

## Mission

The operator's /goal contract says: "continue till you meet ALL MY
REQUIREMENTS without MINIMIZING or rephrasing or compressing or
conflating". When sovereign-os surfaces operator-stated content
(hook drops / mandate rows / raw dump sections), three failure modes
must be prevented at push-time:

1. **Silent paraphrase** — agent "improves" operator's exact phrasing
   ("synchronous writes" → "blocking writes"; "Magician symmetry" →
   "symmetric topology"; "Proto-Programing" silently corrected to
   "Proto-Programming"). The operator's exact words ARE the spec.
2. **Silent compression** — agent shortens lists ("the 6 -mavx512*
   flags" → "the AVX-512 flag set"; "tank/models recordsize 1M lz4
   redundant_metadata=most" → "tank/models tuned"). Loses operator's
   exact specification.
3. **Silent conflation** — agent merges distinct concepts ("Pulse
   Core + Weaver" → "the orchestration layer"; "Q4_K_M or IQ4_NL" →
   "quantized model"). Loses operator's distinctions.

SDD-037 codifies the verbatim-preservation pattern proven across
R355-R366 so future agents apply the same shape uniformly + L1 lint
catches drift in the pattern itself.

## The contract — every verbatim-preservation round MUST

### 1. Identify operator-verbatim content

Source candidates:
- A section of `docs/src/sain-01-master-spec.md` (verbatim from
  master spec dump)
- A macro-arc plan section (verbatim from macro-arc plan dump)
- A new hook drop ("§1b operator spec drop", "/goal directive")
- A new mandate row's operator-verbatim quote

If content lives only in a prose doc (`docs/src/...`), it's a
candidate. If it's already in `scripts/intelligence/architecture-qa.py`
or `scripts/intelligence/coverage-map.py`, it's covered.

### 2. Surface as a discoverable operator-pull verb

Pick the right home:
- **Architectural Q&A / explanatory text** → extend
  `architecture-qa concepts` (C-NN entries)
- **Operator-actionable settings table** → new
  `sovereign-osctl <topic> show/verify/scaffold` verb (e.g.
  R358 state-fabric, R359 network-topology)
- **Stated axis demand** → coverage-map A-NN entry binding it to ≥1
  implementing verb
- **Process / build contract** → bootstrap-verify grid yaml or
  phases yaml (per SDD-028)

### 3. Preserve operator-exact text

```python
# Required schema for every verbatim entry:
{
    "id": "X-NN",
    "<verbatim_field>": "<operator-EXACT text — no rephrasing>",
    "spec_ref": "<source citation: master spec §N / hook drop date>",
    "tags": [...],
    # optional fields per shape
}
```

Verbatim rules:
- Operator typos preserved as-is ("Proto-Programing" → keep missing 'm';
  "planifest" → keep typo; lowercase/uppercase preserved per operator)
- Punctuation preserved (apostrophes in `'Magician' symmetry`; commas
  in `synchronous, lockless`)
- Exact numbers preserved as integers (22548578304 NOT "21 GiB"; 6400 NOT
  "~6.4 GHz"; 31.5 GB/s NOT "~30 GB/s")
- Operator's exact list ordering preserved (e.g., the 4-binary Tetragon
  allowlist appears in operator's exact order)
- Operator's exact list cardinality preserved (`12 packages` from §3.2 →
  catalogue all 12, not "the key packages")

### 4. L3 verbatim-preservation assertions

Every verbatim entry needs ≥1 L3 assertion that loads the JSON output
+ asserts specific operator-EXACT phrases appear in the relevant
field. Pattern:

```bash
out="$(python3 "${SCRIPT}" show <id> --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
field_value = d['item']['<verbatim_field>']
must_have_phrases = [
    '<operator-exact phrase 1>',
    '<operator-exact phrase 2>',
    # ...
]
for phrase in must_have_phrases:
    assert phrase in field_value, f'missing verbatim phrase: {phrase!r}'
"
```

Recommended ≥5 specific phrases per entry. The phrases are chosen to
catch the most likely paraphrase drift (e.g., "synchronous writes"
catches "blocking writes"; "32MB of L3 cache" catches "32 MB L3"
which loses the operator's exact spacing).

### 5. Bidirectional consistency (optional, for code-bearing entries)

When the verbatim entry has a corresponding shipped implementation
(e.g., C-14 Tetragon TracingPolicy has a shipped policy YAML in
`scripts/hooks/post-install/tetragon-policy-load.sh`), add a bidirectional
L3 assertion that the operator-stated text appears in BOTH places.
Neither side can drift silently.

Example (R362 L3 #4 + #13):
- #4 asserts the 4-binary allowlist appears in the concept text
- #13 asserts the same 4 binaries appear in the shipped policy script

### 6. Implementation deviation documentation

When the shipped implementation refines operator's exact text (e.g.,
operator wrote `sys_execve` but modern Tetragon needs `__x64_sys_execve`),
the concept text MUST explicitly document the refinement so operator
can audit it. Example (C-14):

```python
"explanation": ("... operator-verbatim §4 TracingPolicy YAML: "
                  "[full operator text]. "
                  "Implementation note: shipped policy uses "
                  "__x64_sys_execve (architecture-specific syscall "
                  "prefix per modern Tetragon convention) ... while "
                  "preserving the operator's 4-binary allowlist exactly.")
```

### 7. Coverage-map back-link

Every new verbatim surface SHOULD have a coverage-map A-NN row that
cites it as an implementing verb. Future operator-pull "what coverage
do I have for X?" needs the back-link.

## Current shipped surface

After R355-R366 (12 rounds), the verbatim-preservation surface spans:

**Verb / catalog surfaces:**
| Round | Verb | Source(s) | Entries |
|-------|------|-----------|---------|
| R355 | `architecture-qa questions` | §13 | 4 Q-NN |
| R355 | `architecture-qa gotchas` | §14 | 3 G-NN |
| R356 | `ccd-pinning show/verify/recommend` | §19.2 | 3 layers |
| R357 | `architecture-qa concepts` | §15-16 + §19 + Block 6 | C-01..C-05 |
| R358 | `state-fabric layout/verify/scaffold` | §7.1 + §7.2 | 4 files + 3 props |
| R359 | `network-topology show/verify/scaffold` | §8 + §8.1 | 2 NICs + diagram |
| R360 | `architecture-qa concepts` (cont.) | §10 + §11 + §17.1 + §20 + §21 | C-06..C-10 |
| R361 | `architecture-qa concepts` (cont.) | §5 + §9 + §18 | C-11..C-13 |
| R362 | `architecture-qa concepts` (cont.) | §3 + §4/§4.1 | C-14..C-15 |
| R363 | `architecture-qa concepts` (cont.) | §1/§1.1/§1.2 + §3.2 + §23 + dump-tail | C-16..C-19 |
| R364 | `architecture-qa concepts` (cont.) | macro-arc plan post-Plan refinements | C-20..C-23 |
| R365 | `coverage axes/show/audit/search` | hook drops + mandate + raw dumps | 30 A-NN |
| R366 | `repl modes/show/exec/shell` | hook drop 2026-05-17 | 4 modes |

**Total verbatim entries: ~70 catalogued items + ~378 operator-exact
phrases mechanized at push-time.**

**Master spec sections covered (20):**
§1, §1.1, §1.2, §3, §3.2, §4, §4.1, §5, §7.1, §7.2, §8, §8.1, §9,
§10, §11, §13, §14, §15-16, §17.1, §18, §19, §19.1, §19.2, §20, §21,
§22, §23, Block 6.

**Macro-arc plan sections covered (4):**
Post-Plan refinement #1 SFIF, #2 IaC quality bar, #3 Debian-as-Ark,
#4 Q-016 distro reconsideration.

**Dump-tail additions covered:**
DFlash operator quote + arxiv 2602.06036 + 2 HF model candidates.

## L1 lint enforcement

`tests/lint/test_verbatim_preservation_doctrine.py` (R367) pins:

- This SDD-037 file carries the 7 required sections (Mission, Contract,
  Current shipped surface, L1 lint enforcement, What this SDD does NOT
  do, Future verbatim-surface additions, Doctrine evolution).
- `scripts/intelligence/architecture-qa.py` has ≥4 Q-NN questions,
  ≥3 G-NN gotchas, ≥10 C-NN concepts.
- `scripts/intelligence/coverage-map.py` has ≥30 A-NN axes.
- Every architecture-qa item has non-empty `spec_ref` ≥10 chars.
- Every coverage-map axis has ≥1 implementing verb.
- The 4-binary Tetragon allowlist bidirectional consistency
  (R362-pattern): allowlist appears in BOTH the C-14 concept text AND
  `scripts/hooks/post-install/tetragon-policy-load.sh`.

`tests/lint/test_verbatim_spec_ref_format.py` (R368) pins:

- Every Q-NN / G-NN / C-NN `spec_ref` matches one of the recognized
  operator-citation patterns (`master spec §N` / `master spec Block N`
  / `master spec dump-tail` / `macro-arc plan dump <date>` /
  `operator overlay <date>` / `/goal directive <date>`). Catches
  agents fabricating non-existent citation forms.
- Every `master spec §N` reference cites a section number that exists
  in the master spec (§1..§23 + §N.M subsections). Catches fabricated
  section refs like §99.
- The concept catalog cites ≥10 distinct master spec sections
  (top-level). Proves coverage breadth, not just depth on one section.
- Every coverage-map axis `source` matches a known origin pattern
  (`hook drop <date>` / `/goal directive <date>` / `mandate row …` /
  `macro-arc plan dump <date>`).
- Every coverage-map `implementing_verbs` entry starts with
  `sovereign-osctl ` / `systemctl ` / `# ` (catches placeholder verbs
  / typos that wouldn't actually dispatch).

## What this SDD does NOT do

- It does NOT specify which master spec sections to verbatim-pin —
  it specifies HOW to verbatim-pin when a section is targeted.
- It does NOT prevent future rephrasing — that's the L3 phrase
  assertions' job. SDD-037 documents the doctrine; L3 enforces it.
- It does NOT replace prose docs at `docs/src/...` — those remain the
  authoritative source. SDD-037 mandates that operator-pull verbs
  ADDITIONALLY surface the content as queryable + L3-pinned.
- It does NOT mandate that EVERY operator word be preserved — only
  the operator's substantive content. Stylistic comments like "I
  guess" or "honestly" don't need verbatim pinning unless operator
  attaches semantic weight (operator's "I trust you to break down
  planify and continue" — the verb "planify" IS operator-semantic
  weight and would be preserved).
- It does NOT enforce 100% operator-typo preservation — when operator
  ALSO uses the correct spelling later (e.g., operator wrote both
  "Microsoft Macro Assembler" full + "MASM" abbrev), the concept
  text can use the canonical form. The TYPO preservation rule fires
  only when the typo IS the only operator-stated form.

## Future verbatim-surface additions

Future verbatim-pinning candidates (no commitment, just discoverable):

- **§2 Sovereign Forge tmpfs kernel build commands** — operator's
  verbatim 64GB tmpfs setup + GCC 14 toolchain install command list.
  Currently covered by bootstrap phases.yaml + sovereign-osctl
  bootstrap phases; could add a concept C-NN with verbatim shell.
- **§6 Implementation Ledger 4-item next-steps list** — operator's
  4 named phase outcomes. Lower urgency since §11/§12 + bootstrap
  phases already cover the chronological order.
- **§4.1 friction-audit script verbatim** — already shipped at
  `scripts/hooks/{pre,post}-install/friction-audit*.sh`. A concept
  C-NN that surfaces the operator-verbatim audit logic would close
  the meta-loop.
- **Hook drop NEW §1b spec drops** — every future operator §1b drop
  needs the same pattern. SDD-037 documents the template.

## Doctrine evolution

If the operator drops a new §1b spec or shifts an existing verbatim
section:

1. Identify the affected verbatim surface (architecture-qa concept /
   coverage-map axis / state-fabric / network-topology / etc).
2. Update the verbatim field with operator's new exact text — do NOT
   merge with old text unless operator says additive ("its not because
   I add something that you can discard everything I asked you before").
3. Update L3 phrase assertions to match new operator-exact phrases.
4. If the new text contradicts old verbatim, ASK operator (per /goal
   "or JUST ask me question if you are lost") — never silently merge
   contradictory operator statements.
5. Cross-link from coverage-map axis to the new verbatim surface.
6. R285 quarterly review tallies the verbatim-surface tally.

The verbatim-preservation surface is intended to grow asymptotically
toward "every operator-stated content block in every dump" — currently
~70 entries, capable of hosting hundreds via overlay-extension without
changing script structure.
