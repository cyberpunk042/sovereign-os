# SDD conflict-resolution log (SDD-980)

> Append-only cross-session ledger. Each entry records a parallel-session SDD
> collision the auto-resolver handled (or could not), the deterministic rule it
> applied, and the residual follow-ups. `.gitattributes merge=union` keeps every
> session's entries across merges — so it also serves as the seed of the
> session-to-session / session-to-operator message board (see SDD-980).
>
> Format per entry: a `## <UTC timestamp> — <from-session> → <to>` header, then
> WHAT / RULE / ACTION / VERIFY / FURTHER-NEEDS lines.

## 2026-07-21 — chromofold-integration → control-bits (SDD-500 band collision)

- **WHAT:** a post-merge collision — both `control-bits` (M002 bit-machine per-token
  token-law, `docs/sdd/500-per-token-token-law-bitset.md` + SDD-501..504) and
  `chromofold-integration` (`docs/sdd/500-chromofold-compressed-domain-integration.md`)
  claimed SDD band **500–599** and both wrote a `docs/sdd/500-*.md`. Two files at
  number 500; two SESSIONS rows on the same band (SDD-100 disjoint-band violation).
- **RULE:** the earlier-merged / established occupant keeps the band; the later,
  single-SDD newcomer moves to the next free disjoint block. `control-bits` is on
  origin (SDD-500..504, #265–#270) with 5 SDDs; `chromofold-integration` had one
  local SDD. Next free 100-block per the SDD-100 descent (600→500→400) = **400–499**.
- **ACTION (manual — the auto-resolver could not choose: BOTH declared 500–599, so
  neither was the in-band "intruder"):** renumbered `chromofold-integration` →
  band **400–499**, `SDD-500 → SDD-400` (`E11.M500 → E11.M400`, `Q-500-* → Q-400-*`).
  Renamed the SDD file to `400-chromofold-compressed-domain-integration.md`; updated
  the SESSIONS row + README band table + INDEX row + mandate row (chromofold only —
  control-bits' SDD-500 rows untouched) + every chromofold code/doc ref; re-synced the
  app-shell GROUPS into all panels; regenerated sdd-catalog / crate-inventory / rustdoc
  catalog. Also fixed two union-merge count artifacts: `systemd/system/README.md`
  (duplicate 130/131 lines → 131) and `context.md` (duplicate `workspace crates` line
  → single, counts refreshed to 725 crates / 215 sdd).
- **VERIFY:** `test_sdd_numbers_unique`, `test_session_registry`,
  `test_sdd_band_declaration_matches_number`, `test_context_md_counts`,
  `test_systemd_install_coverage`, `test_mdbook_catalog_sync` + the full
  panel/dashboard/systemd sweep (2141 passed, 0 failed); chromofold crates
  fmt+test green; control-bits SDD-500 refs confirmed intact.
- **FURTHER-NEEDS:** none — bands are disjoint again (chromofold 400–499,
  control-bits 500–599). SESSIONS "next free block" prose descent now points below 400.
