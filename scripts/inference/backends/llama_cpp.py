"""llama.cpp adapter — fallback path + old-workstation primary backend.

GGUF models on CPU or GPU (CUDA / Vulkan); operator picks via build.
Used on sain-01 as the non-DFlash quantized-model fallback on the
3090 when vLLM isn't suitable; primary backend on old-workstation.
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
    ):
        super().__init__(config)
        self.n_gpu_layers = n_gpu_layers
        self.ctx_size = ctx_size
        self.tier = tier

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
    def for_sain01_fallback(cls, model_path: str) -> "LlamaCppBackend":
        """Used on the 3090 (VFIO-bound) as a non-DFlash fallback."""
        cfg = BackendConfig(
            model_path=model_path,
            host="127.0.0.1",
            port=8085,
            cuda_visible_devices="0",
        )
        return cls(cfg, n_gpu_layers=999, ctx_size=8192, tier="logic_engine")
