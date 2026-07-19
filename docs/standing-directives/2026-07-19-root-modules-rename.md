# Standing directive — upstream rename: root-ghostproxy → root-modules

**Status**: ACTIVE (operator directive, 2026-07-19, verbatim — logged BEFORE acting)
**Audience**: every session touching the SDD-046 binding, provision/bake, or cross-repo references

## Verbatim operator statements (sacrosanct — do not paraphrase)

Upstream rename (in the root-modules repo session):

> "root-ghostproxy has just been renamed into root-modules. lets update the repo as such. its at first and by default a root or home folder upgrader, evolver and secondly you can install supplementary modules like the ghostproxy combo."

sovereign-os follow-up:

> "sovereign-os too think its root-ghostproxy I think, lets solve that"

## What this directive establishes

1. The sister repo `cyberpunk042/root-ghostproxy` is now **`cyberpunk042/root-modules`**. First and by default a root/home folder upgrader + evolver; "ghostproxy" now names the **proxy module combo** (L2 bridge + Suricata + PolarProxy) — exactly the half the SDD-046 binding keeps OFF.
2. sovereign-os references, hooks, profile wiring, and the lint gate track the new name (see D-023 for the full rename/keep split). Legacy env names + pre-rename checkouts stay honored.
3. Plain-"ghostproxy" wire identifiers (metrics `sovereign_os_ghostproxy_endpoint_*`, unit `sovereign-ghostproxy-verify.*`, `*_GHOSTPROXY_*` gate envs, legacy profile key) are KEPT for contract stability — a future migration is an operator decision, not implied by this directive.

## Cross-references

- Decision record: `docs/decisions.md` D-023
- Binding SDD: `docs/sdd/046-root-modules-endpoint-binding.md`
- Upstream rename directive log: `cyberpunk042/root-modules wiki/log/2026-07-19-rename-root-modules-directive.md`
