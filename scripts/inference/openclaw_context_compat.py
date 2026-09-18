"""Version-shape-gated repair for OpenClaw's local context accounting.

No configuration, history, or model limit changes. Unknown upstream forms fail
closed. Backups preserve the pre-patch runtime; profile sync reapplies repairs
after package updates only when the exact supported source is still present.
"""
from pathlib import Path

MARKER = "// sovereign-context-accounting-v1"


def patch_runtime(dist: Path, dry_run=False, log=print):
    helper = Path(__file__).with_name("openclaw-context-accounting.js").read_text()
    boundary = "\t\tconst contextUsage = message?.role === \"assistant\" ? message.usage?.contextUsage : void 0;"
    seed = "estimateRenderedPromptTokens(params) + (boundary ? 0 : replay?.prefixTokens ?? 0)"
    recovery = "\tconst preflightRecovery = input.attempt.preflightRecovery;"
    succeeded = "\t\tif (compactResult.compacted) {"
    specs = [
        ("helpers-*.js", "function resolveProviderContextBoundary(messages)", [
            (boundary, "\t\tconst measured = sovereignMeasuredBoundary(message, index);\n\t\tif (measured) return measured;\n" + boundary),
            (seed, '(boundary?.includesSystemPrompt ? estimateRenderedPromptTokens({ ...params, systemPrompt: "" }) : estimateRenderedPromptTokens(params)) + (boundary ? 0 : replay?.prefixTokens ?? 0)'),
        ]),
        ("embedded-agent-*.js", "async function recoverEmbeddedRunOverflow(input)", [
            (recovery, recovery + "\n\tsovereignRecoveryProgress(input);"),
            (succeeded, succeeded + "\n\t\t\tif (input.provider === \"sovereign\") input.state.sovereignCompacted = true;"),
        ]),
    ]
    pending = []
    for glob, anchor, replacements in specs:
        matches = [p for p in dist.glob(glob) if anchor in p.read_text()]
        if not matches:
            raise RuntimeError(f"unsupported OpenClaw runtime: missing {anchor}")
        for path in matches:
            source = path.read_text()
            if MARKER in source:
                continue
            for old, new in replacements:
                if source.count(old) != 1:
                    raise RuntimeError(f"unsupported OpenClaw runtime shape in {path.name}")
                source = source.replace(old, new, 1)
            pending.append((path, MARKER + "\n" + helper + "\n" + source))
    for path, source in pending:
        log(f"{'would repair' if dry_run else 'repairing'} context accounting: {path.name}")
        if dry_run:
            continue
        backup = path.with_suffix(path.suffix + ".sovereign-context-v1.bak")
        if not backup.exists():
            backup.write_bytes(path.read_bytes())
            backup.chmod(0o600)
        path.write_text(source)
    return bool(pending) and not dry_run
