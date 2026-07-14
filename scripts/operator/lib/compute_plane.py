#!/usr/bin/env python3
"""
scripts/operator/lib/compute_plane.py — the Sovereign Compute Plane (Phase 1).

One scheduler that places compute claims across the box's devices by LIVE free
VRAM, so a GPU job never OOMs the box. Phase 1 is host-side (the RTX PRO 6000 +
CPU); Phase 2 adds model residents, Phase 3 the RTX-4090 passthrough VM as a
device.

It mirrors the M075 SRP doctrine (`crates/sovereign-srp-scheduler`): the roles
Conductor (CPU, ternary), Logic (RTX 5090, 32 GB, D-022), Oracle (Blackwell
PRO 6000, fp16, 96 GB), and placement by precision + VRAM fit. The canonical
placement rule lives in the Rust `place()`; this is the runtime the jobs daemon
consults for host-side, live-VRAM fit. Stdlib only.

A **claim** is a device + an amount of VRAM held for the life of a job (Phase 2:
also a model resident). `place()` returns a device whose *effective* free VRAM
(live free − outstanding claims) covers the need, preferring the requested role,
else `None` (the caller queues and retries).
"""
from __future__ import annotations

import shutil
import subprocess
import threading

# SRP roles + their canonical device envelope (mirrors HardwareTarget::for_role).
ROLE_CONDUCTOR = "conductor"   # CPU — ternary
ROLE_LOGIC = "logic"           # RTX 5090 32 GB — quantized (D-022; internal PCIEX16_2)
ROLE_ORACLE = "oracle"         # Blackwell PRO 6000 Max-Q 96 GB — fp16

_lock = threading.RLock()


def _role_for_gpu(name: str) -> str:
    """Map a probed GPU name to an SRP role by the M075 topology (D-022).

    The Logic Engine tier runs on the RTX 5090 (internal PCIEX16_2, 32 GB).
    The PRO 6000 Max-Q / Blackwell big-VRAM card is the Oracle. The RTX 4090
    OcuLink eGPU is the DSpark speculative-decode draft, not a Trinity tier —
    but if it is the only quantized device present it stands in for Logic.
    """
    n = name.lower()
    # PRO 6000 / Blackwell big-VRAM → Oracle (the deep-reasoning device).
    if "pro 6000" in n or "blackwell" in n or "6000" in n:
        return ROLE_ORACLE
    # RTX 5090 → Logic (D-022). 4090/3090 stand in as the quantized tier when
    # the 5090 is absent.
    if "5090" in n or "4090" in n or "3090" in n:
        return ROLE_LOGIC
    # Anything else big/unknown → Oracle (deep-reasoning fallback).
    return ROLE_ORACLE


def probe_gpus() -> list[dict]:
    """Live per-GPU VRAM via nvidia-smi. Empty when there's no nvidia-smi
    (degrade-safe → the plane is CPU-only)."""
    if shutil.which("nvidia-smi") is None:
        return []
    try:
        out = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=index,name,memory.total,memory.used,memory.free",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10, check=False).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    gpus = []
    for line in out.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 5 or not parts[0].isdigit():
            continue
        idx, name, total, _used, free = parts[:5]
        gpus.append({
            "key": f"gpu{idx}",
            "role": _role_for_gpu(name),
            "name": name,
            "total_gb": round(int(total) / 1024, 1),
            "live_free_gb": round(int(free) / 1024, 1),
        })
    return gpus


class ComputePlane:
    """Device inventory + outstanding claims + VRAM-fit placement."""

    def __init__(self, probe=probe_gpus):
        self._probe = probe
        # claim_id -> {device, vram_gb, kind, job}
        self._claims: dict[str, dict] = {}

    # ── inventory ────────────────────────────────────────────────────────
    def _probe_devices(self) -> list[dict]:
        """The device inventory WITHOUT claim math — the CPU (Conductor) + every
        probed GPU, each with total + live free VRAM. The probe (nvidia-smi) is slow
        I/O, so it runs OUTSIDE `_lock`."""
        devices = [{
            "key": "cpu", "role": ROLE_CONDUCTOR, "name": "Host CPU (bitnet.cpp)",
            "total_gb": 0.0, "live_free_gb": 0.0,  # CPU has no VRAM budget (ternary)
        }]
        devices.extend(self._probe())
        return devices

    def _annotate_claims(self, devices: list[dict]) -> list[dict]:
        """Add `claimed_gb` + `effective_free_gb` (live free − claims) to probed
        devices. The CALLER must hold `_lock` (claims are read here)."""
        for d in devices:
            d["claimed_gb"] = round(
                sum(c["vram_gb"] for c in self._claims.values() if c["device"] == d["key"]), 1)
            # the CPU always has room for CPU/ternary work (no VRAM gate)
            d["effective_free_gb"] = (
                float("inf") if d["key"] == "cpu"
                else round(max(0.0, d["live_free_gb"] - d["claimed_gb"]), 1))
        return devices

    def _devices(self) -> list[dict]:
        """The device list with live free VRAM + this plane's claims subtracted."""
        devices = self._probe_devices()
        with _lock:
            self._annotate_claims(devices)
        return devices

    @staticmethod
    def _pick(devices: list[dict], need: float, role_pref: str | None) -> str | None:
        """Pick a device key from ALREADY-annotated `devices` whose effective free
        VRAM covers `need` (preferring `role_pref`, then most headroom); `need <= 0`
        → the CPU (Conductor); None when nothing fits."""
        if need <= 0:
            cpu = next((d for d in devices if d["key"] == "cpu"), None)
            return cpu["key"] if cpu else (devices[0]["key"] if devices else None)
        fit = [d for d in devices if d["key"] != "cpu" and d["effective_free_gb"] >= need]
        if not fit:
            return None
        preferred = [d for d in fit if role_pref and d["role"] == role_pref]
        return max(preferred or fit, key=lambda d: d["effective_free_gb"])["key"]

    # ── placement ────────────────────────────────────────────────────────
    def place(self, need_gb: float, role_pref: str | None = None) -> str | None:
        """Return a device key whose effective free VRAM covers `need_gb` (read-only
        preview). For admission use `place_and_claim` — `place` then a separate
        `claim` is a check-then-act race that can over-commit a device."""
        return self._pick(self._devices(), float(need_gb or 0), role_pref)

    def place_and_claim(self, claim_id: str, need_gb: float, role_pref: str | None = None,
                        kind: str = "job", job: str = "") -> str | None:
        """ATOMIC place + claim under a SINGLE `_lock` hold: pick a fitting device and
        record the claim before any other admission can observe the (now-committed)
        VRAM. Two concurrent jobs can no longer both pass the fit check on the same
        device and over-commit it — the invariant behind 'a GPU job never OOMs the
        box'. Returns the device key, or None when nothing fits (the caller queues)."""
        need = float(need_gb or 0)
        devices = self._probe_devices()  # slow probe OUTSIDE the lock
        with _lock:
            self._annotate_claims(devices)
            device = self._pick(devices, need, role_pref)
            if device is None:
                return None
            if need > 0:
                self._claims[claim_id] = {
                    "device": device, "vram_gb": need, "kind": kind, "job": job}
            return device

    def claim(self, claim_id: str, device: str, vram_gb: float, kind: str = "job", job: str = "") -> dict:
        with _lock:
            rec = {"device": device, "vram_gb": float(vram_gb or 0), "kind": kind, "job": job}
            self._claims[claim_id] = rec
            return dict(rec, id=claim_id)

    def release(self, claim_id: str) -> bool:
        with _lock:
            return self._claims.pop(claim_id, None) is not None

    def held(self, claim_id: str) -> bool:
        with _lock:
            return claim_id in self._claims

    # ── observability ────────────────────────────────────────────────────
    def state(self) -> dict:
        devices = self._devices()
        with _lock:
            claims = [dict(c, id=k) for k, c in self._claims.items()]
        gpu_devices = [d for d in devices if d["key"] != "cpu"]
        return {
            "devices": [
                {**d, "effective_free_gb": (None if d["effective_free_gb"] == float("inf")
                                            else d["effective_free_gb"])}
                for d in devices
            ],
            "claims": claims,
            "summary": {
                "gpus": len(gpu_devices),
                "total_vram_gb": round(sum(d["total_gb"] for d in gpu_devices), 1),
                "free_vram_gb": round(sum(d["live_free_gb"] for d in gpu_devices), 1),
                "claimed_vram_gb": round(sum(c["vram_gb"] for c in claims), 1),
                "active_claims": len(claims),
            },
        }
