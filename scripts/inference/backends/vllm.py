"""vLLM adapter — Logic Engine (RTX 5090 internal secondary, D-022) + Oracle Core (Blackwell PRO 6000).

Per SDD-011 + E109 (DFlash integration): vLLM v0.20.1+ pinned.
DFlash speculative-decoding drafts wired when the target model has a
pre-trained DFlash checkpoint on Z-Lab's HuggingFace org.

DSpark (DeepSeek, 2026-06-27) — the DFlash successor — is preferred when a
DSpark draft checkpoint is supplied: it reuses the DFlash draft backbone plus a
lightweight Markov head, verifies a DSpark-5 (5-token) block in one target
forward pass via rejection sampling, and is LOSSLESS. Opt-in but on-by-default
(see config/inference/m083-...yaml `dspark:` + scripts/inference/dspark-wrap.sh).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.backend import Backend, BackendConfig  # noqa: E402


class VllmBackend(Backend):
    name = "vllm"
    tier = "logic_engine"  # or "oracle_core" — operator picks via tier= arg

    MIN_VERSION = "0.20.1"  # required for DFlash

    def __init__(
        self,
        config: BackendConfig,
        *,
        tier: str = "logic_engine",
        tensor_parallel_size: int = 1,
        dflash_draft_model: str | None = None,
        dspark_draft_model: str | None = None,
        dspark_num_speculative_tokens: int = 5,  # DSpark-5 (shipped default)
        kv_cache_dtype: str = "auto",  # "fp8" for Blackwell deep-context per L0
        gpu_memory_utilization: float = 0.92,
    ):
        super().__init__(config)
        self.tier = tier
        self.tensor_parallel_size = tensor_parallel_size
        self.dflash_draft_model = dflash_draft_model
        self.dspark_draft_model = dspark_draft_model
        self.dspark_num_speculative_tokens = dspark_num_speculative_tokens
        self.kv_cache_dtype = kv_cache_dtype
        self.gpu_memory_utilization = gpu_memory_utilization

    def start_command(self) -> list[str]:
        argv: list[str] = []

        # Podman wrapping for the Logic Engine (RTX 5090 internal secondary
        # per D-022; the container path is retained per §17.1 and is also the
        # opt-in VFIO-isolation path for the RTX 4090 eGPU DSpark draft);
        # native for the Blackwell PRO 6000 (Oracle Core).
        if self.config.podman:
            argv += [
                "podman", "run", "--rm",
                "--device", "nvidia.com/gpu=all",
                "--security-opt=label=disable",
                "-v", "/mnt/vault/models:/models:ro",
                "-p", f"{self.config.port}:{self.config.port}",
                "--name", f"vllm-{self.tier}",
                "vllm/vllm-openai:latest",
            ]
        else:
            argv += ["python3", "-m", "vllm.entrypoints.openai.api_server"]

        argv += [
            "--model", self.config.model_path,
            "--host", self.config.host,
            "--port", str(self.config.port),
            "--tensor-parallel-size", str(self.tensor_parallel_size),
            "--gpu-memory-utilization", str(self.gpu_memory_utilization),
        ]

        if self.kv_cache_dtype != "auto":
            argv += ["--kv-cache-dtype", self.kv_cache_dtype]

        # Speculative decoding — only when a draft checkpoint is supplied;
        # vLLM 0.20.1+ understands the speculative-config flag. DSpark (the
        # DFlash successor, DeepSeek 2026-06-27) is PREFERRED when present: it
        # reuses the DFlash draft backbone + a Markov head, verifies a DSpark-5
        # block by rejection sampling, and is LOSSLESS. Falls back to plain
        # DFlash (E109) when only a DFlash checkpoint is given.
        if self.dspark_draft_model:
            argv += [
                "--speculative-config",
                f'{{"model": "{self.dspark_draft_model}", "method": "dspark", '
                f'"num_speculative_tokens": {self.dspark_num_speculative_tokens}}}',
            ]
        elif self.dflash_draft_model:
            argv += [
                "--speculative-config",
                f'{{"model": "{self.dflash_draft_model}", "method": "dflash"}}',
            ]

        argv += self.config.extra_args
        return argv

    def health_url(self) -> str:
        return f"http://{self.config.host}:{self.config.port}/v1/models"

    @classmethod
    def for_logic_engine(cls, model_path: str) -> "VllmBackend":
        cfg = BackendConfig(
            model_path=model_path,
            host="127.0.0.1",
            port=8082,
            podman=True,
            # 4090 is VFIO-bound; podman injects it as the only visible GPU
            cuda_visible_devices="0",
        )
        return cls(cfg, tier="logic_engine", tensor_parallel_size=1)

    @classmethod
    def for_oracle_core(
        cls,
        model_path: str,
        *,
        dflash_draft_model: str | None = None,
        dspark_draft_model: str | None = None,
        dspark_num_speculative_tokens: int = 5,
        kv_cache_dtype: str = "fp8",
    ) -> "VllmBackend":
        cfg = BackendConfig(
            model_path=model_path,
            host="127.0.0.1",
            port=8083,
            podman=False,
            # Blackwell is host-resident; assumes index 0 after VFIO
            # claims the 4090 (which lives in a separate IOMMU group).
            cuda_visible_devices="0",
        )
        return cls(
            cfg,
            tier="oracle_core",
            tensor_parallel_size=1,
            dflash_draft_model=dflash_draft_model,
            dspark_draft_model=dspark_draft_model,
            dspark_num_speculative_tokens=dspark_num_speculative_tokens,
            kv_cache_dtype=kv_cache_dtype,
            gpu_memory_utilization=0.92,
        )
