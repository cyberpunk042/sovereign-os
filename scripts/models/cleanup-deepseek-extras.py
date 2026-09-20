#!/usr/bin/env python3
"""One-time operator-approved cleanup; dry-run unless --apply is supplied.

DANGER: deletes only the 36 inventoried surplus files, not directories or
other models. Deleted public artifacts can be downloaded again, not undeleted.
"""
import argparse
import json
from pathlib import Path
import stat
import subprocess

ROOT = Path('/mnt/vault/models/DeepSeek-R1-Distill-Llama-70B-Q4_K_M')
KEEP = ROOT / 'DeepSeek-R1-Distill-Llama-70B-Q4_K_M.gguf'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if ROOT.resolve() != ROOT or KEEP.is_symlink() or KEEP.stat().st_size != 42520396448:
        raise SystemExit('Refusing: model directory or preserved Q4_K_M differs from inspection')
    entries = json.loads(Path(__file__).with_name('deepseek-cleanup-20260920.json').read_text())
    selected = []
    for entry in entries:
        path = Path(entry['path'])
        if not path.is_relative_to(ROOT) or 'Q4_K_M' in str(path.relative_to(ROOT)) or path.resolve() != path:
            raise SystemExit('Refusing: manifest target outside approved scope')
        if not path.exists():
            continue
        st = path.lstat()
        if not stat.S_ISREG(st.st_mode) or (st.st_size, st.st_ino, st.st_mtime_ns) != (entry['size'], entry['inode'], entry['mtime_ns']):
            raise SystemExit(f'Refusing: file changed since inspection: {path}')
        if args.apply and subprocess.run(['fuser','-s',str(path)], check=False).returncode != 1:
            raise SystemExit(f'Refusing: file open or open-file check failed: {path}')
        selected.append(path)
    print(f'{len(selected)} approved surplus files; {sum(p.stat().st_blocks*512 for p in selected)/2**30:.2f} GiB allocated')
    for path in selected:
        print(('DELETE ' if args.apply else 'WOULD DELETE ') + str(path))
    if args.apply:
        for path in selected:
            path.unlink()
        print('Cleanup complete. Q4_K_M and all other model directories preserved.')
    else:
        print('Dry run only. Use --apply after reviewing; root authentication is required.')


if __name__ == '__main__':
    main()
