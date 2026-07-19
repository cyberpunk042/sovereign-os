"""notifykit.config — gating config with the operator's sacrosanct semantics.

Three rules from the 2026-07-19 verbatim directive are load-bearing here:

1. "for sms it will require a high priority, high urgency by default and
   it will be conifugrable"
     → builtin twilio gate default: min_priority=high, min_urgency=high;
       every gate key is operator-overridable in the TOML.

2. "for if with no SMS at all then the starting point is resent require
   urgent and high priority"
     → when NO twilio channel is configured+enabled, the resend gate's
       STARTING POINT becomes min_priority=high, min_urgency=urgent.
       (With SMS present, resend starts at normal/normal.)

3. "the user will be able to use and play with those such as setting a
   global default override and only those set to static value modified
   remain as is"
     → a [global_override] table sweeps every channel gate key EXCEPT
       keys the user pinned static. A key is pinned by writing it as an
       inline table: min_priority = { value = "high", static = true }.

Resolution order per gate key (weakest wins first, later layers win):
    builtin default (incl. rule-2 conditional)
  → channel TOML value
  → [global_override] value — SKIPPED for keys pinned static
Static pins beat the global override; that is the whole point of rule 3.

Secrets: config carries env-var NAMES ("env:VAR_NAME" values), never
values — SDD-009, same contract as sovereign-os notify.toml.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:  # py3.11+
    import tomllib
except ImportError:  # pragma: no cover
    tomllib = None

from .event import PRIORITY_LEVELS, URGENCY_LEVELS

GATE_KEYS = ("min_priority", "min_urgency")

# Rule 1 + baseline defaults. Channel keys are notifykit channel kinds.
BUILTIN_GATES: dict[str, dict[str, str]] = {
    "file":    {"min_priority": "min", "min_urgency": "min"},
    "ntfy":    {"min_priority": "min", "min_urgency": "min"},
    "webhook": {"min_priority": "min", "min_urgency": "min"},
    "resend":  {"min_priority": "normal", "min_urgency": "normal"},
    "twilio":  {"min_priority": "high", "min_urgency": "high"},  # rule 1
    "mock":    {"min_priority": "min", "min_urgency": "min"},
}

# Rule 2 — the no-SMS starting point for resend.
NO_SMS_RESEND_GATE = {"min_priority": "high", "min_urgency": "urgent"}


def _valid_level(key: str, value: str) -> str:
    levels = PRIORITY_LEVELS if key == "min_priority" else URGENCY_LEVELS
    if value not in levels:
        raise ValueError(f"{key}={value!r} not in {levels}")
    return value


@dataclass
class ChannelConfig:
    kind: str                       # file | ntfy | webhook | resend | twilio | mock
    name: str                       # instance name (usually == kind)
    enabled: bool = False
    gate: dict[str, str] = field(default_factory=dict)
    static_keys: set[str] = field(default_factory=set)
    options: dict[str, Any] = field(default_factory=dict)  # channel-specific

    def resolve_env(self, key: str, default: str = "") -> str:
        """SDD-009 env-var indirection: option values of the form
        'env:VAR' resolve to os.environ['VAR'] at delivery time."""
        raw = str(self.options.get(key, default) or default)
        if raw.startswith("env:"):
            return os.environ.get(raw[4:], "")
        return raw


@dataclass
class NotifyConfig:
    channels: dict[str, ChannelConfig] = field(default_factory=dict)
    global_override: dict[str, str] = field(default_factory=dict)

    # ---------- construction ----------

    @classmethod
    def load(cls, path: str | Path) -> "NotifyConfig":
        if tomllib is None:  # pragma: no cover
            raise RuntimeError("tomllib unavailable (python >= 3.11 required)")
        with open(path, "rb") as fh:
            doc = tomllib.load(fh)
        return cls.from_dict(doc)

    @classmethod
    def from_dict(cls, doc: dict[str, Any]) -> "NotifyConfig":
        cfg = cls()
        raw_override = doc.get("global_override") or {}
        for k, v in raw_override.items():
            if k in GATE_KEYS:
                cfg.global_override[k] = _valid_level(k, str(v))
        for name, ch in (doc.get("channels") or {}).items():
            kind = str(ch.get("kind", name))
            channel = ChannelConfig(kind=kind, name=name)
            channel.enabled = bool(ch.get("enabled", False))
            for key in GATE_KEYS:
                if key in ch:
                    raw = ch[key]
                    # static pin: min_priority = {value="high", static=true}
                    if isinstance(raw, dict):
                        channel.gate[key] = _valid_level(key, str(raw.get("value")))
                        if raw.get("static"):
                            channel.static_keys.add(key)
                    else:
                        channel.gate[key] = _valid_level(key, str(raw))
            channel.options = {
                k: v for k, v in ch.items()
                if k not in ("kind", "enabled", *GATE_KEYS)
            }
            cfg.channels[name] = channel
        return cfg

    # ---------- the semantics ----------

    def sms_present(self) -> bool:
        """Rule 2 trigger: is ANY twilio channel configured AND enabled?
        'with no SMS at all' = no enabled twilio channel."""
        return any(
            c.kind == "twilio" and c.enabled for c in self.channels.values()
        )

    def effective_gate(self, name: str) -> dict[str, str]:
        """The gate a channel actually enforces, after the full
        resolution order (builtin → channel value → global override
        except static pins)."""
        channel = self.channels[name]
        # layer 1 — builtin default (with the rule-2 conditional)
        if channel.kind == "resend" and not self.sms_present():
            gate = dict(NO_SMS_RESEND_GATE)
        else:
            gate = dict(BUILTIN_GATES.get(channel.kind,
                                          {"min_priority": "min",
                                           "min_urgency": "min"}))
        # layer 2 — channel TOML values
        gate.update(channel.gate)
        # layer 3 — global override, EXCEPT static pins (rule 3)
        for key, value in self.global_override.items():
            if key not in channel.static_keys:
                gate[key] = value
        return gate
