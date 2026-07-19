"""notifykit.event — the two-axis event model.

Operator verbatim carries BOTH axes, separately: "for sms it will
require a high priority, high urgency by default" · "resent require
urgent and high priority". Operator-confirmed shape (2026-07-19):
ntfy-style 5 levels per axis, so gates express as thresholds and the
priority axis maps 1:1 onto the ntfy `Priority` header (1-5).
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Ordered weakest → strongest. Index = ntfy Priority (1-5) for priority.
PRIORITY_LEVELS: tuple[str, ...] = ("min", "low", "normal", "high", "max")
URGENCY_LEVELS: tuple[str, ...] = ("min", "low", "normal", "high", "urgent")


def priority_rank(level: str) -> int:
    return PRIORITY_LEVELS.index(level)


def urgency_rank(level: str) -> int:
    return URGENCY_LEVELS.index(level)


@dataclass
class Event:
    """One notification event flowing through the channel registry."""

    title: str
    message: str
    priority: str = "normal"
    urgency: str = "normal"
    tags: list[str] = field(default_factory=list)
    click_url: str = ""
    source: str = ""          # emitting subsystem (e.g. "wikiops", "r228")
    dedupe_key: str = ""      # consumer-managed; the library does not dedupe
    # Markdown-frontmatter-style properties & metadata (operator verbatim
    # 2026-07-19: "important:true and such markdown properties & metadata
    # as much has in the header") — attached by triggers; passed through
    # to channels/receipt consumers untouched.
    props: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.priority not in PRIORITY_LEVELS:
            raise ValueError(
                f"priority {self.priority!r} not in {PRIORITY_LEVELS}"
            )
        if self.urgency not in URGENCY_LEVELS:
            raise ValueError(
                f"urgency {self.urgency!r} not in {URGENCY_LEVELS}"
            )

    @property
    def ntfy_priority(self) -> int:
        """ntfy Priority header value (1-5) from the priority axis."""
        return priority_rank(self.priority) + 1

    def meets(self, min_priority: str, min_urgency: str) -> bool:
        """Threshold gate over BOTH axes (AND, per the verbatim
        'high priority, high urgency')."""
        return (
            priority_rank(self.priority) >= priority_rank(min_priority)
            and urgency_rank(self.urgency) >= urgency_rank(min_urgency)
        )
