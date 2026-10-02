#!/usr/bin/env python3
"""Install a version-checked, opt-in OpenClaw metadata trace. No inference changes."""
from pathlib import Path
import argparse


def patch(text):
    marker = 'import { traceManagedRequest } from "./sovereign-request-diagnostics.mjs";\n'
    if marker in text:
        return text
    start = text.index('function createOpenAICompletionsExtraBodyWrapper(')
    end = text.index('\nfunction ', start + 1)
    block = text[start:end]
    before = 'return streamWithPayloadPatch(underlying, model, context, options, (payloadObj) => {'
    after = 'return traceManagedRequest(model, options, (tracedOptions) => streamWithPayloadPatch(underlying, model, context, tracedOptions, (payloadObj) => {'
    if block.count(before) != 1 or block.count('\n\t\t});') != 1:
        raise ValueError('Unrecognized OpenClaw wrapper; refusing patch')
    block = block.replace(before, after).replace('\n\t\t});', '\n\t\t}));')
    return marker + text[:start] + block + text[end:]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dist', type=Path)
    parser.add_argument('--disable', action='store_true', help='Stop recording immediately; no gateway restart required')
    args = parser.parse_args()
    directory = Path.home() / '.openclaw/diagnostics'
    if args.disable:
        (directory / 'request-hashes.enabled').unlink(missing_ok=True)
        print('Request diagnostics disabled; existing metadata retained.')
        return
    if args.dist is None:
        parser.error('--dist is required for installation')
    directory.mkdir(mode=0o700, exist_ok=True)
    if directory.is_symlink() or directory.stat().st_mode & 0o077:
        raise ValueError('Diagnostics directory must be private and not a symlink')
    matches = [p for p in args.dist.glob('extra-params-*.js') if 'function createOpenAICompletionsExtraBodyWrapper(' in p.read_text()]
    if len(matches) != 1:
        raise ValueError('Expected exactly one matching OpenClaw bundle')
    target = matches[0]
    original = target.read_text()
    updated = patch(original)
    backup = target.with_suffix('.js.request-diagnostics.bak')
    if not backup.exists():
        backup.write_text(original)
    (args.dist / 'sovereign-request-diagnostics.mjs').write_text(Path(__file__).with_name('openclaw-request-diagnostics.mjs').read_text())
    target.write_text(updated)
    (directory / 'request-hashes.enabled').touch(mode=0o600)
    print(f'Installed opt-in metadata diagnostics in {target.name}; restart gateway to load.')


if __name__ == '__main__':
    main()
