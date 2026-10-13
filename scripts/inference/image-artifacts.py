#!/usr/bin/env python3
"""Permanently delete one strictly named generated PNG; no arbitrary paths."""
import argparse
import json
from pathlib import Path
import re

GALLERY = Path('/var/lib/sovereign-os/image-generation')
NAME = re.compile(r'[0-9TZ_-]{8,64}\.png')


def delete(name, gallery=GALLERY):
    if not NAME.fullmatch(name):
        raise ValueError('Invalid artifact name')
    source = gallery / name
    if source.is_symlink() or not source.is_file():
        raise ValueError('Artifact missing or not a regular file')
    source.unlink()
    return {'removed': name, 'recoverable': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('verb', choices=['delete'])
    parser.add_argument('name')
    parser.add_argument('--confirm', action='store_true', required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(delete(args.name)))
    except (ValueError, OSError) as exc:
        parser.exit(1, str(exc) + '\n')
