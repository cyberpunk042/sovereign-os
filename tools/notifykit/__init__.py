"""notifykit — the shared notification library (2026-07-19).

Operator directive (verbatim, sacrosanct — full text at
docs/standing-directives/2026-07-19-notification-wiki-operability-mode.md):
"it will allow to sent notifications of ntly and resend emails and even
twillo, [...] for sms it will require a high priority, high urgency by
default and it will be conifugrable and for if with no SMS at all then
the starting point is resent require urgent and high priority. and the
user will be able to use and play with those such as setting a global
default override and only those set to static value modified remain as
is."

Operator-confirmed design (2026-07-19 evaluation):
  - a NEW SHARED LIBRARY (this package) that sovereign-os R228 and
    sister projects both consume — stdlib-only core (urllib; no SDKs),
    secrets by env-var NAME indirection per SDD-009, mock channels for
    credential-free testing (continuity-orchestrator registry pattern);
  - TWO AXES, ntfy-style 5 levels each:
      priority ∈ {min, low, normal, high, max}
      urgency  ∈ {min, low, normal, high, urgent}
  - per-channel gates as thresholds over both axes; verbatim defaults
    encoded in config.py;
  - global default override with per-key static pins.

Prior art consumed (per the research doc): sovereign-os R228
dispatch.py (env-var indirection, channel shape), openfleet
fleet/infra/ntfy_client.py @3d993f5c (priority map + topic routing),
continuity-orchestrator adapters (Resend/Twilio semantics, receipts,
retryable classification, mock registry).
"""

from .event import Event, PRIORITY_LEVELS, URGENCY_LEVELS  # noqa: F401
from .config import NotifyConfig  # noqa: F401
from .registry import ChannelRegistry, Receipt  # noqa: F401
