#!/usr/bin/env python3
"""Losslessly reverse Diffusers FLUX.2 tensor layout for stable-diffusion.cpp.

Source artifacts stay untouched. No dtype changes. Validate against Diffusers'
official forward converter before atomically publishing a derived checkpoint.
"""
import json
from pathlib import Path


def reverse(source):
    import torch
    result = {}
    basic = {
        'x_embedder': 'img_in', 'context_embedder': 'txt_in',
        'time_guidance_embed.timestep_embedder.linear_1': 'time_in.in_layer',
        'time_guidance_embed.timestep_embedder.linear_2': 'time_in.out_layer',
        'time_guidance_embed.guidance_embedder.linear_1': 'guidance_in.in_layer',
        'time_guidance_embed.guidance_embedder.linear_2': 'guidance_in.out_layer',
        'double_stream_modulation_img.linear': 'double_stream_modulation_img.lin',
        'double_stream_modulation_txt.linear': 'double_stream_modulation_txt.lin',
        'single_stream_modulation.linear': 'single_stream_modulation.lin',
        'proj_out': 'final_layer.linear',
    }
    single = {'attn.to_qkv_mlp_proj': 'linear1', 'attn.to_out': 'linear2',
              'attn.norm_q': 'norm.query_norm', 'attn.norm_k': 'norm.key_norm'}
    double = {'attn.norm_q': 'img_attn.norm.query_norm', 'attn.norm_k': 'img_attn.norm.key_norm',
              'attn.to_out.0': 'img_attn.proj', 'ff.linear_in': 'img_mlp.0', 'ff.linear_out': 'img_mlp.2',
              'attn.norm_added_q': 'txt_attn.norm.query_norm', 'attn.norm_added_k': 'txt_attn.norm.key_norm',
              'attn.to_add_out': 'txt_attn.proj', 'ff_context.linear_in': 'txt_mlp.0', 'ff_context.linear_out': 'txt_mlp.2'}
    for key, tensor in source.items():
        stem, param = key.rsplit('.', 1)
        if stem in basic:
            result[basic[stem] + '.' + param] = tensor
        elif stem == 'norm_out.linear':
            a, b = tensor.chunk(2, dim=0)
            result['final_layer.adaLN_modulation.1.' + param] = torch.cat((b, a), dim=0)
        elif key.startswith('single_transformer_blocks.'):
            _, index, rest = stem.split('.', 2)
            name = single[rest]
            result[f'single_blocks.{index}.{name}.' + ('scale' if name.startswith('norm.') else param)] = tensor
        elif key.startswith('transformer_blocks.'):
            _, index, rest = stem.split('.', 2)
            if rest in ('attn.to_q', 'attn.to_k', 'attn.to_v', 'attn.add_q_proj', 'attn.add_k_proj', 'attn.add_v_proj'):
                if rest not in ('attn.to_q', 'attn.add_q_proj'):
                    continue
                image = rest == 'attn.to_q'
                names = ('to_q', 'to_k', 'to_v') if image else ('add_q_proj', 'add_k_proj', 'add_v_proj')
                result[f'double_blocks.{index}.{"img" if image else "txt"}_attn.qkv.{param}'] = torch.cat(
                    [source[f'transformer_blocks.{index}.attn.{n}.{param}'] for n in names], dim=0)
            else:
                name = double[rest]
                result[f'double_blocks.{index}.{name}.' + ('scale' if '.norm.' in name else param)] = tensor
        else:
            raise ValueError(f'Unmapped tensor: {key}')
    return result


def main():
    import torch
    from safetensors.torch import load_file, save_file
    from diffusers.loaders.single_file_utils import convert_flux2_transformer_checkpoint_to_diffusers
    root = Path(__file__).resolve().parents[2]
    source = Path('/mnt/vault/models/FLUX.2-dev/transformer')
    dest = root / '.runtime/image-artifacts/flux2-dev-native-bf16.safetensors'
    dest.parent.mkdir(parents=True, exist_ok=True)
    index = json.loads((source / 'diffusion_pytorch_model.safetensors.index.json').read_text())
    tensors = {}
    for shard in sorted(set(index['weight_map'].values())):
        tensors.update(load_file(source / shard))
    converted = reverse(tensors)
    restored = convert_flux2_transformer_checkpoint_to_diffusers(dict(converted))
    if restored.keys() != tensors.keys() or any(
        restored[k].dtype != v.dtype or not torch.equal(restored[k], v) for k, v in tensors.items()):
        raise ValueError('Lossless tensor round-trip verification failed')
    print(f'Verified {len(tensors)} tensors bit-exact; writing native BF16 checkpoint', flush=True)
    temp = dest.with_suffix('.incomplete')
    save_file(converted, temp, metadata={'source_revision': '26afe3a78bb242c0a8bb181dcc8937bb16e5c66c',
                                         'conversion': 'lossless tensor renaming, QKV fusion and scale/shift permutation'})
    temp.replace(dest)
    print(f'Complete: {dest} ({dest.stat().st_size} bytes)', flush=True)


if __name__ == '__main__':
    main()
