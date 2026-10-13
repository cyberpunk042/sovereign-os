import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('artifacts', Path(__file__).resolve().parents[1] / 'scripts/inference/image-artifacts.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_permanent_delete_only_selected_file(tmp_path):
    name = '2026-10-10T111429Z-8188.png'
    image = tmp_path / name
    image.write_bytes(b'test fixture')
    other = tmp_path / 'unrelated.png'
    other.write_bytes(b'preserve')
    assert module.delete(name, tmp_path)['recoverable'] is False
    assert not image.exists()
    assert other.exists()
    assert not (tmp_path / '.trash').exists()


@pytest.mark.parametrize('name', ['../outside.png', '/tmp/image.png', 'x.png', '2026-10-10T111429Z-8188.png'])
def test_reject_invalid_or_missing(tmp_path, name):
    with pytest.raises(ValueError):
        module.delete(name, tmp_path)


def test_reject_symlink(tmp_path):
    target = tmp_path / 'keep'
    target.write_bytes(b'preserve')
    name = '2026-10-10T111429Z-8188.png'
    (tmp_path / name).symlink_to(target)
    with pytest.raises(ValueError):
        module.delete(name, tmp_path)
    assert target.exists()
