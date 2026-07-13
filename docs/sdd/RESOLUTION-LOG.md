# SDD conflict-resolution log (SDD-980)

> Append-only cross-session ledger. Each entry records a parallel-session SDD
> collision the auto-resolver handled (or could not), the deterministic rule it
> applied, and the residual follow-ups. `.gitattributes merge=union` keeps every
> session's entries across merges — so it also serves as the seed of the
> session-to-session / session-to-operator message board (see SDD-980).
>
> Format per entry: a `## <UTC timestamp> — <from-session> → <to>` header, then
> WHAT / RULE / ACTION / VERIFY / FURTHER-NEEDS lines.
