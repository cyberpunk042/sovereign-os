"""notifykit.channels — delivery channels. Stdlib-only (urllib), no SDKs.

Adapted from the operator-cited prior art (research doc, 2026-07-19):
  ntfy   — openfleet fleet/infra/ntfy_client.py @3d993f5c: priority →
           ntfy Priority header (1-5), optional priority→topic routing,
           Tags + Click headers.
  resend — continuity-orchestrator src/adapters/email_resend.py:
           first-'#'-line → subject, plain REST POST (no SDK here —
           https://api.resend.com/emails with a Bearer key).
  twilio — continuity-orchestrator src/adapters/sms_twilio.py: E.164
           check, body truncation at 480 chars (3 concatenated
           segments), plain REST POST with basic auth (no SDK).
  file   — sovereign-os R228 dispatch.py: JSONL local audit trail.
  mock   — continuity-orchestrator adapters/registry.py mock_mode:
           records instead of delivering; credential-free tests.

Secrets NEVER live in config values — env-var NAME indirection
(ChannelConfig.resolve_env, SDD-009).
"""

from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from .config import ChannelConfig
from .event import Event

MAX_SMS_LEN = 480  # 3 concatenated segments — continuity precedent


@dataclass
class Receipt:
    channel: str
    kind: str
    ok: bool
    skipped: bool = False       # gated / disabled — not a failure
    detail: str = ""
    delivery_id: str = ""
    at: float = field(default_factory=time.time)


def _http(req: urllib.request.Request, timeout: float = 10.0) -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", "replace")
            return 200 <= resp.status < 300, body
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:200]}"
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        return False, str(e)


class Channel:
    """Base channel: validate() then send(). Subclasses stay tiny."""

    def __init__(self, cfg: ChannelConfig):
        self.cfg = cfg

    @property
    def name(self) -> str:
        return self.cfg.name

    def validate(self) -> tuple[bool, str]:
        return True, ""

    def send(self, event: Event) -> Receipt:  # pragma: no cover - abstract
        raise NotImplementedError


class FileChannel(Channel):
    def validate(self) -> tuple[bool, str]:
        return (True, "") if self.cfg.options.get("path") else (False, "no path")

    def send(self, event: Event) -> Receipt:
        path = str(self.cfg.options["path"])
        try:
            import os
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({
                    "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "title": event.title, "message": event.message,
                    "priority": event.priority, "urgency": event.urgency,
                    "source": event.source, "tags": event.tags,
                }) + "\n")
            return Receipt(self.name, "file", ok=True, delivery_id=path)
        except OSError as e:
            return Receipt(self.name, "file", ok=False, detail=str(e))


class NtfyChannel(Channel):
    def validate(self) -> tuple[bool, str]:
        if not self.cfg.resolve_env("base_url", "https://ntfy.sh"):
            return False, "no base_url"
        if not self._topic_for("normal"):
            return False, "no topic"
        return True, ""

    def _topic_for(self, priority: str) -> str:
        # openfleet TOPIC_MAP pattern: optional [options.topic_by_priority]
        by_prio = self.cfg.options.get("topic_by_priority") or {}
        return str(by_prio.get(priority, "") or self.cfg.resolve_env("topic"))

    def send(self, event: Event) -> Receipt:
        base = self.cfg.resolve_env("base_url", "https://ntfy.sh").rstrip("/")
        topic = self._topic_for(event.priority)
        headers = {
            "Title": event.title[:120],
            "Priority": str(event.ntfy_priority),
        }
        if event.tags:
            headers["Tags"] = ",".join(event.tags)
        if event.click_url:
            headers["Click"] = event.click_url
        token = self.cfg.resolve_env("token")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(
            f"{base}/{topic}", data=event.message.encode(), headers=headers
        )
        ok, body = _http(req)
        return Receipt(self.name, "ntfy", ok=ok,
                       detail="" if ok else body, delivery_id=topic)


class WebhookChannel(Channel):
    def validate(self) -> tuple[bool, str]:
        return (True, "") if self.cfg.resolve_env("url") else (False, "no url")

    def send(self, event: Event) -> Receipt:
        payload = json.dumps({
            "title": event.title, "message": event.message,
            "priority": event.priority, "urgency": event.urgency,
            "source": event.source, "tags": event.tags,
        }).encode()
        req = urllib.request.Request(
            self.cfg.resolve_env("url"), data=payload,
            headers={"Content-Type": "application/json"},
        )
        ok, body = _http(req)
        return Receipt(self.name, "webhook", ok=ok, detail="" if ok else body)


class ResendChannel(Channel):
    """Resend email via plain REST (POST https://api.resend.com/emails)."""

    def validate(self) -> tuple[bool, str]:
        if not self.cfg.resolve_env("api_key"):
            return False, "no api_key (set the env var the config names)"
        if not self.cfg.resolve_env("from_email"):
            return False, "no from_email"
        if not self.cfg.resolve_env("to_email"):
            return False, "no to_email"
        return True, ""

    def send(self, event: Event) -> Receipt:
        payload = json.dumps({
            "from": self.cfg.resolve_env("from_email"),
            "to": [self.cfg.resolve_env("to_email")],
            "subject": event.title,
            "text": event.message,
            "headers": {"X-Notifykit-Source": event.source or "notifykit"},
        }).encode()
        req = urllib.request.Request(
            str(self.cfg.options.get("api_url", "https://api.resend.com/emails")),
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.cfg.resolve_env('api_key')}",
            },
        )
        ok, body = _http(req)
        delivery_id = ""
        if ok:
            try:
                delivery_id = json.loads(body).get("id", "")
            except json.JSONDecodeError:
                pass
        return Receipt(self.name, "resend", ok=ok,
                       detail="" if ok else body, delivery_id=delivery_id)


class TwilioChannel(Channel):
    """Twilio SMS via plain REST (Messages.json, basic auth)."""

    def validate(self) -> tuple[bool, str]:
        sid = self.cfg.resolve_env("account_sid")
        if not sid:
            return False, "no account_sid"
        if not self.cfg.resolve_env("auth_token"):
            return False, "no auth_token"
        for key in ("from_number", "to_number"):
            num = self.cfg.resolve_env(key)
            if not num:
                return False, f"no {key}"
            if not num.startswith("+") or len(num) < 10:
                return False, f"{key} must be E.164 (+...): {num!r}"
        return True, ""

    def send(self, event: Event) -> Receipt:
        sid = self.cfg.resolve_env("account_sid")
        body_text = f"{event.title}: {event.message}"
        if len(body_text) > MAX_SMS_LEN:
            body_text = body_text[: MAX_SMS_LEN - 3] + "..."
        api_url = str(self.cfg.options.get(
            "api_url",
            f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
        ))
        data = urllib.parse.urlencode({
            "From": self.cfg.resolve_env("from_number"),
            "To": self.cfg.resolve_env("to_number"),
            "Body": body_text,
        }).encode()
        auth = base64.b64encode(
            f"{sid}:{self.cfg.resolve_env('auth_token')}".encode()
        ).decode()
        req = urllib.request.Request(
            api_url, data=data,
            headers={"Authorization": f"Basic {auth}"},
        )
        ok, body = _http(req)
        delivery_id = ""
        if ok:
            try:
                delivery_id = json.loads(body).get("sid", "")
            except json.JSONDecodeError:
                pass
        return Receipt(self.name, "twilio", ok=ok,
                       detail="" if ok else body, delivery_id=delivery_id)


class MockChannel(Channel):
    """Records events instead of delivering — credential-free tests."""

    def __init__(self, cfg: ChannelConfig):
        super().__init__(cfg)
        self.sent: list[Event] = []

    def send(self, event: Event) -> Receipt:
        self.sent.append(event)
        return Receipt(self.name, "mock", ok=True, delivery_id=str(len(self.sent)))


CHANNEL_KINDS: dict[str, type[Channel]] = {
    "file": FileChannel,
    "ntfy": NtfyChannel,
    "webhook": WebhookChannel,
    "resend": ResendChannel,
    "twilio": TwilioChannel,
    "mock": MockChannel,
}


def build_channel(cfg: ChannelConfig) -> Channel:
    cls = CHANNEL_KINDS.get(cfg.kind)
    if cls is None:
        raise ValueError(f"unknown channel kind {cfg.kind!r}")
    return cls(cfg)


def _unused(*_: Any) -> None:  # keep dataclass import surface stable
    return None
