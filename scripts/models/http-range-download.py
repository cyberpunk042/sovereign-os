"""Pinned, resumable HTTP fallback. Never trust a range without its bounds."""
import hashlib
import os
from pathlib import Path
import re
import time
from urllib.parse import quote


def download(repo, revision, files, target, token=None, client=None, sleep=time.sleep):
    import httpx
    owned = client is None
    client = client or httpx.Client(follow_redirects=True, timeout=90)
    try:
        for item in files:
            dest = Path(target) / item['path']
            dest.parent.mkdir(parents=True, exist_ok=True)
            partial = dest.with_name(dest.name + '.' + revision + '.http.incomplete')
            if dest.is_symlink() or partial.is_symlink():
                raise ValueError('Symlink download target')
            if dest.is_file() and dest.stat().st_size == item['size']:
                continue  # Worker still verifies every final checksum.
            if partial.exists() and partial.stat().st_size > item['size']:
                raise ValueError('Oversized partial artifact')
            failures = 0
            while (partial.stat().st_size if partial.exists() else 0) < item['size']:
                start = partial.stat().st_size if partial.exists() else 0
                end = min(start + 64 * 1024**2, item['size']) - 1
                url = f'https://huggingface.co/{repo}/resolve/{revision}/{quote(item["path"], safe="/")}'
                headers = {'Range': f'bytes={start}-{end}', 'Accept-Encoding': 'identity', 'Cache-Control': 'no-cache'}
                if token:
                    headers['Authorization'] = 'Bearer ' + token
                try:
                    with client.stream('GET', url, headers=headers) as response:
                        response.raise_for_status()
                        match = re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)', response.headers.get('content-range', ''))
                        if response.status_code != 206 or not match or tuple(map(int, match.groups())) != (start, end, item['size']):
                            # Small non-LFS files may ignore Range only for a full request.
                            if not (response.status_code == 200 and start == 0 and end + 1 == item['size']):
                                raise ValueError('Server did not honor exact requested range')
                        written = 0
                        with partial.open('ab') as handle:
                            for chunk in response.iter_bytes(1024 * 1024):
                                if written + len(chunk) > end - start + 1:
                                    raise ValueError('Response exceeded requested range')
                                handle.write(chunk)
                                written += len(chunk)
                            handle.flush()
                            os.fsync(handle.fileno())
                        if written != end - start + 1:
                            raise httpx.ReadError('Short range response')
                    failures = 0
                except httpx.HTTPError:
                    failures += 1
                    if failures >= 5:
                        raise
                    sleep(min(2 ** failures, 20))
            if item.get('sha256'):
                with partial.open('rb') as handle:
                    if hashlib.file_digest(handle, 'sha256').hexdigest() != item['sha256']:
                        raise ValueError('HTTP artifact checksum mismatch; partial preserved')
            partial.replace(dest)
    finally:
        if owned:
            client.close()
