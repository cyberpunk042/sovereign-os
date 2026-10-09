#!/usr/bin/env python3
"""Repackage the local Mistral language-model weights without changing tensors."""
import json
from pathlib import Path
from safetensors.torch import load_file, save_file

root = Path(__file__).resolve().parents[2]
source = Path('/mnt/vault/models/FLUX.2-dev/text_encoder')
index = json.loads((source / 'model.safetensors.index.json').read_text())
tensors = {}
for shard in sorted(set(index['weight_map'].values())):
    for name, tensor in load_file(source / shard).items():
        if name.startswith('language_model.'):
            tensors[name.removeprefix('language_model.')] = tensor
assert 'model.embed_tokens.weight' in tensors and 'model.norm.weight' in tensors
dest = root / '.runtime/image-artifacts/flux2-text-encoder-native-bf16.safetensors'
temp = dest.with_suffix('.incomplete')
print(f'Writing {len(tensors)} unchanged language tensors with native names', flush=True)
save_file(tensors, temp, metadata={'source_revision': '26afe3a78bb242c0a8bb181dcc8937bb16e5c66c',
                                  'conversion': 'remove language_model prefix; tensor data and dtype unchanged'})
temp.replace(dest)
print(f'Complete: {dest} ({dest.stat().st_size} bytes)', flush=True)
