"""Shape-gated OpenClaw recovery fix; never repeat tools or alter normal turns."""
from pathlib import Path

MARKER = '// sovereign-settled-finalization-v1'
ANCHOR = 'function buildRestrictedFinalizationAttempt(attempt) {'
OLD = '\t\toperation: "settled-tool-finalization",\n\t\tdisableTools: true,\n\t\tdisableTrajectory: true,'
NEW = '\t\t...sovereignFinalizationParams(attempt),\n' + OLD


def patch_runtime(dist: Path, dry_run=False, log=print):
    helper = Path(__file__).with_name('openclaw-finalization-params.js').read_text()
    matches = [p for p in dist.glob('builtin-openclaw-*.js') if ANCHOR in p.read_text()]
    if not matches:
        raise RuntimeError('unsupported OpenClaw finalization runtime: missing restricted attempt')
    pending = []
    for path in matches:
        source = path.read_text()
        if MARKER in source:
            if source.count(NEW) != 1 or helper not in source:
                raise RuntimeError(f'altered OpenClaw finalization patch: {path.name}')
            continue
        start = source.index(ANCHOR)
        end = source.find('\n}', start)
        if end < 0 or source[start:end].count(OLD) != 1 or source.count(OLD) != 1:
            raise RuntimeError(f'unsupported OpenClaw finalization shape: {path.name}')
        pending.append((path, MARKER + '\n' + helper + '\n' + source.replace(OLD, NEW, 1)))
    for path, source in pending:
        log(f'{"would repair" if dry_run else "repairing"} isolated finalization: {path.name}')
        if dry_run:
            continue
        backup = path.with_suffix(path.suffix + '.sovereign-finalization-v1.bak')
        if not backup.exists():
            backup.write_bytes(path.read_bytes())
            backup.chmod(0o600)
        path.write_text(source)
    return bool(pending) and not dry_run
