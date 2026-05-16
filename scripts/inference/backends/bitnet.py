"""bitnet.cpp adapter — Pulse-tier CPU inference.

Per SDD-005 sain-01 profile + SDD-011 inference stack: Pulse pinned to
CCD 0 (cores 0-5) on Zen 5; ternary `microsoft/bitnet-b1.58-2B-4T`
default model; TL2 x86 kernels.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.backend import Backend, BackendConfig  # noqa: E402


class BitnetBackend(Backend):
    name = "bitnet"
    tier = "pulse"

    DEFAULT_MODEL = "microsoft/bitnet-b1.58-2B-4T"
    DEFAULT_THREADS = 12  # 6 cores * 2 SMT on CCD 0
    DEFAULT_KERNEL = "TL2"  # x86 default; alternatives: I2_S

    def start_command(self) -> list[str]:
        argv: list[str] = []

        # Pin to CCD 0 cores by default; operator overrides via
        # config.cpu_affinity
        affinity = self.config.cpu_affinity or "0-5"
        argv += ["taskset", "-c", affinity]

        # bitnet.cpp ships a `llama-cli`-style binary; convention name:
        # `bitnet-cli` (operator may symlink or set BITNET_BIN env)
        bitnet_bin = self.config.env.get("BITNET_BIN", "bitnet-cli")
        argv += [bitnet_bin]

        # Model + server flags
        argv += ["-m", self.config.model_path]
        argv += ["--host", self.config.host, "--port", str(self.config.port)]
        argv += ["-t", str(self.DEFAULT_THREADS)]

        # Kernel choice (TL2 for x86; I2_S for lossless)
        kernel = self.config.env.get("BITNET_KERNEL", self.DEFAULT_KERNEL)
        argv += ["--kernel", kernel]

        # Server mode (OpenAI-compatible if bitnet.cpp build supports)
        argv += ["--server"]

        argv += self.config.extra_args
        return argv

    def health_url(self) -> str:
        return f"http://{self.config.host}:{self.config.port}/v1/models"

    @classmethod
    def default_config(cls) -> BackendConfig:
        return BackendConfig(
            model_path=cls.DEFAULT_MODEL,
            host="127.0.0.1",
            port=8081,
            cpu_affinity="0-5",
        )
