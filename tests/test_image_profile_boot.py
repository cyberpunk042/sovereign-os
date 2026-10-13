import importlib.util
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('boot', ROOT / 'scripts/inference/image-profile-boot.py')
boot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boot)


def test_companion_excludes_logic_and_keeps_image_oracle(tmp_path):
    marker = tmp_path / 'marker'
    marker.write_text('codernext-image-companion')
    assert not boot.permitted('logic', root=ROOT, marker=marker)
    assert boot.permitted('oracle', root=ROOT, marker=marker)
    assert boot.permitted('image', 'Qwen-Image-2.1-Uncensored-BF16', ROOT, marker)
    assert not boot.permitted('image', 'FLUX.2-dev', ROOT, marker)


def test_chat_profile_skips_image(tmp_path):
    directory = tmp_path / 'profiles/orchestration'
    directory.mkdir(parents=True)
    (directory / 'chat.yaml').write_text(yaml.safe_dump({'orchestration_profile': {'id': 'chat'}}))
    marker = tmp_path / 'marker'
    marker.write_text('chat')
    assert boot.permitted('logic', root=tmp_path, marker=marker)
    assert not boot.permitted('image', root=tmp_path, marker=marker)


def test_missing_profile_never_loads_defaults(tmp_path):
    marker = tmp_path / 'marker'
    marker.write_text('missing')
    with pytest.raises(ValueError):
        boot.permitted('logic', root=tmp_path, marker=marker)
