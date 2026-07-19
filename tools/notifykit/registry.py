"""notifykit.registry — the gating dispatcher.

For each configured channel: enabled? → gate met (priority AND urgency
thresholds from NotifyConfig.effective_gate — the full resolution
order incl. the no-SMS rule + global override + static pins)? →
validate? → send. Every outcome is a Receipt — including gated skips,
so the caller can always answer "why did/didn't this fire?".
"""

from __future__ import annotations

from .channels import Receipt, build_channel
from .config import NotifyConfig
from .event import Event


class ChannelRegistry:
    def __init__(self, config: NotifyConfig):
        self.config = config
        self.channels = {
            name: build_channel(cfg) for name, cfg in config.channels.items()
        }

    def dispatch(self, event: Event) -> list[Receipt]:
        receipts: list[Receipt] = []
        for name, channel in self.channels.items():
            cfg = self.config.channels[name]
            if not cfg.enabled:
                receipts.append(Receipt(
                    name, cfg.kind, ok=True, skipped=True, detail="disabled"))
                continue
            gate = self.config.effective_gate(name)
            if not event.meets(gate["min_priority"], gate["min_urgency"]):
                receipts.append(Receipt(
                    name, cfg.kind, ok=True, skipped=True,
                    detail=(
                        f"gated: needs priority>={gate['min_priority']} "
                        f"AND urgency>={gate['min_urgency']}; event is "
                        f"{event.priority}/{event.urgency}"
                    ),
                ))
                continue
            valid, why = channel.validate()
            if not valid:
                receipts.append(Receipt(
                    name, cfg.kind, ok=False, detail=f"invalid config: {why}"))
                continue
            receipts.append(channel.send(event))
        return receipts
