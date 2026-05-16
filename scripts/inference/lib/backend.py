"""Backend adapter contract for the sovereign-os direct inference stack.

Every backend implements two operations:
  - .start_command() → argv list to spawn the backend daemon
  - .health() → bool, is the backend reachable + serving?

Adapters are intentionally minimal — the operator can read each
adapter in one screen and understand exactly what's invoked. No
hidden dispatch.
"""

from __future__ import annotations

import abc
import dataclasses
from typing import Any


@dataclasses.dataclass
class BackendConfig:
    """Runtime-configurable parameters from sovereign-osctl / env vars."""

    model_path: str
    host: str = "127.0.0.1"
    port: int = 8080
    extra_args: list[str] = dataclasses.field(default_factory=list)
    env: dict[str, str] = dataclasses.field(default_factory=dict)
    # Optional substrate-specific options
    podman: bool = False
    cuda_visible_devices: str | None = None
    cpu_affinity: str | None = None  # e.g. "0-5" for taskset

    def merge_env(self, base: dict[str, str] | None = None) -> dict[str, str]:
        merged = dict(base) if base else {}
        merged.update(self.env)
        if self.cuda_visible_devices is not None:
            merged["CUDA_VISIBLE_DEVICES"] = self.cuda_visible_devices
        return merged


class Backend(abc.ABC):
    """Abstract backend interface. Each concrete adapter knows ONE
    inference engine and exposes its launch contract honestly."""

    name: str  # e.g. "bitnet", "vllm", "llama_cpp"
    tier: str  # e.g. "pulse", "logic_engine", "oracle_core"

    def __init__(self, config: BackendConfig):
        self.config = config

    @abc.abstractmethod
    def start_command(self) -> list[str]:
        """Return argv list for spawning the backend daemon.

        The orchestrator (a sibling shell script) is responsible for
        actually running the command; adapters just describe it.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def health_url(self) -> str:
        """URL to hit for health check (e.g. http://127.0.0.1:8080/v1/models)."""
        raise NotImplementedError

    def describe(self) -> dict[str, Any]:
        """Diagnostic dump for sovereign-osctl inference status."""
        return {
            "backend": self.name,
            "tier": self.tier,
            "host": self.config.host,
            "port": self.config.port,
            "model_path": self.config.model_path,
            "podman": self.config.podman,
            "cuda_visible_devices": self.config.cuda_visible_devices,
            "cpu_affinity": self.config.cpu_affinity,
            "extra_args": self.config.extra_args,
        }
