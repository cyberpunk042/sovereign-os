"""llama.cpp adapter — fallback path + old-workstation primary backend.

GGUF models on CPU or GPU (CUDA / Vulkan); operator picks via build.
Used on sain-01 as the non-DFlash quantized-model fallback on the
4090 when vLLM isn't suitable; primary backend on old-workstation.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.backend import Backend, BackendConfig  # noqa: E402


class LlamaCppBackend(Backend):
    name = "llama_cpp"
    tier = "logic_engine"  # default; override for old-workstation primary

    DEFAULT_N_GPU_LAYERS = 999  # offload everything to GPU when present

    def __init__(
        self,
        config: BackendConfig,
        *,
        n_gpu_layers: int = DEFAULT_N_GPU_LAYERS,
        ctx_size: int = 8192,
        tier: str = "logic_engine",
        tensor_split: str | None = None,
        lora_path: str | None = None,
        lora_scale: float | None = None,
    ):
        super().__init__(config)
        self.n_gpu_layers = n_gpu_layers
        self.ctx_size = ctx_size
        self.tier = tier
        # Comma-separated per-GPU layer ratio for multi-GPU splits, e.g. "11,8"
        # for the dual-Turing workstation (RTX 2080 Ti 11 GB + RTX 2080 8 GB).
        # llama.cpp handles UNEVEN VRAM by ratio — the key reason it, not vLLM
        # (symmetric tensor-parallel), fits an asymmetric consumer-GPU pair.
        self.tensor_split = tensor_split
        # SDD-715 LoRA-as-profiles (M046 E0442): overlay a GGUF adapter on the
        # frozen ternary base WITHOUT merging (E0443 "Do Not Merge Too Early").
        # lora_scale None → plain `--lora`; a float → `--lora-scaled <path> <s>`.
        # The base stays shared; the adapter is a hot-swappable behavioral overlay.
        self.lora_path = lora_path
        self.lora_scale = lora_scale

    def start_command(self) -> list[str]:
        # llama.cpp's server binary; operator-installed (apt or build)
        argv: list[str] = []

        if self.config.cpu_affinity:
            argv += ["taskset", "-c", self.config.cpu_affinity]

        llama_bin = self.config.env.get("LLAMA_BIN", "llama-server")
        argv += [llama_bin]

        argv += [
            "-m", self.config.model_path,
            "--host", self.config.host,
            "--port", str(self.config.port),
            "--ctx-size", str(self.ctx_size),
            "-ngl", str(self.n_gpu_layers),
        ]

        if self.tensor_split:
            argv += ["--tensor-split", self.tensor_split]

        if self.lora_path:
            if self.lora_scale is not None:
                argv += ["--lora-scaled", self.lora_path, str(self.lora_scale)]
            else:
                argv += ["--lora", self.lora_path]

        argv += self.config.extra_args
        return argv

    def health_url(self) -> str:
        return f"http://{self.config.host}:{self.config.port}/v1/models"

    @classmethod
    def for_old_workstation(cls, model_path: str) -> "LlamaCppBackend":
        cfg = BackendConfig(
            model_path=model_path,
            host="127.0.0.1",
            port=8084,
        )
        return cls(cfg, n_gpu_layers=999, ctx_size=4096, tier="logic_engine")

    @classmethod
    def for_dual_turing(
        cls,
        model_path: str,
        *,
        port: int = 8083,
        tensor_split: str | None = None,
        ctx_size: int = 4096,
        lora_path: str | None = None,
        lora_scale: float | None = None,
    ) -> "LlamaCppBackend":
        """dual-turing-serving runtime profile (SDD-714): a ternary GGUF on the
        operator's RTX 2080 Ti + RTX 2080 pair. Both cards visible; pass
        tensor_split='11,8' to span a model too large for one card (long
        context), or leave None to keep one model per card. Pass lora_path to
        overlay an M046 LoRA adapter on the frozen base (SDD-715, unmerged)."""
        cfg = BackendConfig(
            model_path=model_path,
            host="127.0.0.1",
            port=port,
            cuda_visible_devices="0,1",
        )
        return cls(
            cfg,
            n_gpu_layers=999,
            ctx_size=ctx_size,
            tier="oracle_core",
            tensor_split=tensor_split,
            lora_path=lora_path,
            lora_scale=lora_scale,
        )

    @classmethod
    def for_sain01_fallback(cls, model_path: str) -> "LlamaCppBackend":
        """Used on the 4090 (VFIO-bound) as a non-DFlash fallback."""
        cfg = BackendConfig(
            model_path=model_path,
            host="127.0.0.1",
            port=8085,
            cuda_visible_devices="0",
        )
        return cls(cfg, n_gpu_layers=999, ctx_size=8192, tier="logic_engine")
