import hashlib
from pathlib import Path
import runpy

import httpx
import pytest

download = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'scripts/models/http-range-download.py'))['download']


def test_resumes_exact_prefix_and_verifies(tmp_path):
    partial = tmp_path / 'model.gguf.rev.http.incomplete'
    partial.write_bytes(b'abc')
    def handler(request):
        assert request.headers['range'] == 'bytes=3-5'
        return httpx.Response(206, headers={'Content-Range': 'bytes 3-5/6'}, content=b'def')
    item = {'path': 'model.gguf', 'size': 6, 'sha256': hashlib.sha256(b'abcdef').hexdigest()}
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        download('test/model', 'rev', [item], tmp_path, client=client)
    assert (tmp_path / 'model.gguf').read_bytes() == b'abcdef'
    assert not partial.exists()


@pytest.mark.parametrize('status,bounds,content', [(200, '', b'abcdef'), (206,'bytes 0-2/6',b'abc'), (206,'bytes 3-5/6',b'bad')])
def test_rejects_wrong_range_or_checksum(tmp_path, status, bounds, content):
    (tmp_path / 'model.gguf.rev.http.incomplete').write_bytes(b'abc')
    item = {'path': 'model.gguf', 'size': 6, 'sha256': hashlib.sha256(b'abcdef').hexdigest()}
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(status, headers={'Content-Range':bounds},content=content))) as client:
        with pytest.raises(ValueError):
            download('test/model','rev',[item],tmp_path,client=client)
    assert not (tmp_path / 'model.gguf').exists()


def test_bounded_retry_leaves_partial(tmp_path):
    count = []
    def handler(request):
        count.append(1)
        raise httpx.ConnectError('private URL must never enter state')
    partial = tmp_path / 'model.gguf.rev.http.incomplete'
    partial.write_bytes(b'abc')
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(httpx.ConnectError):
            download('test/model','rev',[{'path':'model.gguf','size':6}],tmp_path,client=client,sleep=lambda _:None)
    assert len(count) == 5
    assert partial.read_bytes() == b'abc'


def test_auth_not_forwarded_to_storage_host(tmp_path):
    def handler(request):
        if request.url.host == 'huggingface.co':
            assert request.headers['authorization'] == 'Bearer secret'
            return httpx.Response(302, headers={'Location':'https://storage.example/file'})
        assert 'authorization' not in request.headers
        return httpx.Response(206, headers={'Content-Range':'bytes 0-2/3'},content=b'abc')
    with httpx.Client(transport=httpx.MockTransport(handler),follow_redirects=True) as client:
        download('test/model','rev',[{'path':'model.gguf','size':3}],tmp_path,token='secret',client=client)
