//! `sovereign-pii-redact` — keep personal data out of logs and telemetry.
//!
//! A sovereign system that respects the user must not leak their personal data
//! into logs, traces, or anything sent off the device. This crate scans text for
//! the common identifiers and either reports them or rewrites them out.
//!
//! It detects four high-confidence kinds: **email addresses**, **US Social
//! Security numbers** (`###-##-####`), **IPv4 addresses** (with each octet range
//! checked so `999.1.1.1` is not a match), and **credit-card numbers** — the last
//! validated with the **Luhn checksum** over the digits, which rejects the vast
//! majority of random 13–19 digit runs and keeps the false-positive rate low.
//!
//! [`detect`] returns typed [`Detection`]s with byte spans, sorted by position
//! and de-overlapped (longer matches win). [`redact`] returns a copy with each
//! match replaced by a `[KIND]` tag; [`redact_with`] lets you supply the
//! replacement. Detection is deterministic and dependency-free.
//!
//! It is a high-precision heuristic, not a guarantee — it will not catch a name
//! or a novel identifier format — so use it as a privacy *gate*, layered, not as
//! the sole control.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the pii-redact surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A kind of detected PII.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum PiiKind {
    /// An email address.
    Email,
    /// A US Social Security number.
    Ssn,
    /// An IPv4 address.
    IpV4,
    /// A credit-card number (Luhn-valid).
    CreditCard,
}

impl PiiKind {
    /// The default redaction tag for this kind.
    pub fn tag(self) -> &'static str {
        match self {
            PiiKind::Email => "[EMAIL]",
            PiiKind::Ssn => "[SSN]",
            PiiKind::IpV4 => "[IP]",
            PiiKind::CreditCard => "[CARD]",
        }
    }
}

/// One detected PII span.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Detection {
    /// What was found.
    pub kind: PiiKind,
    /// Start byte offset (inclusive).
    pub start: usize,
    /// End byte offset (exclusive).
    pub end: usize,
    /// The matched text.
    pub text: String,
}

/// Detect all PII in `text`, sorted by position with overlaps removed (the
/// earliest, then longest, match wins).
pub fn detect(text: &str) -> Vec<Detection> {
    let bytes = text.as_bytes();
    let mut found = Vec::new();
    found.extend(scan_email(text, bytes));
    found.extend(scan_ssn(text, bytes));
    found.extend(scan_ipv4(text, bytes));
    found.extend(scan_credit_card(text, bytes));

    // sort by start, then by longer span first, and drop overlaps.
    found.sort_by(|a, b| a.start.cmp(&b.start).then(b.end.cmp(&a.end)));
    let mut out: Vec<Detection> = Vec::new();
    let mut last_end = 0usize;
    for d in found {
        if d.start >= last_end {
            last_end = d.end;
            out.push(d);
        }
    }
    out
}

/// Redact `text`, replacing each detection with its default `[KIND]` tag.
pub fn redact(text: &str) -> String {
    redact_with(text, |k| k.tag().to_string())
}

/// Redact `text`, replacing each detection with `replacement(kind)`.
pub fn redact_with(text: &str, replacement: impl Fn(PiiKind) -> String) -> String {
    let dets = detect(text);
    let mut out = String::with_capacity(text.len());
    let mut cursor = 0usize;
    for d in &dets {
        out.push_str(&text[cursor..d.start]);
        out.push_str(&replacement(d.kind));
        cursor = d.end;
    }
    out.push_str(&text[cursor..]);
    out
}

/// Whether `text` contains any PII.
pub fn contains_pii(text: &str) -> bool {
    !detect(text).is_empty()
}

fn is_email_local(b: u8) -> bool {
    b.is_ascii_alphanumeric() || matches!(b, b'.' | b'_' | b'%' | b'+' | b'-')
}
fn is_domain(b: u8) -> bool {
    b.is_ascii_alphanumeric() || matches!(b, b'.' | b'-')
}

fn scan_email(text: &str, b: &[u8]) -> Vec<Detection> {
    let mut out = Vec::new();
    let n = b.len();
    let mut i = 0;
    while i < n {
        if b[i] == b'@' {
            // expand left over local part
            let mut s = i;
            while s > 0 && is_email_local(b[s - 1]) {
                s -= 1;
            }
            // expand right over domain
            let mut e = i + 1;
            while e < n && is_domain(b[e]) {
                e += 1;
            }
            // require a non-empty local, and a domain containing a dot with a TLD
            let local_ok = s < i;
            let domain = &b[i + 1..e];
            let dot = domain.iter().position(|&c| c == b'.');
            let tld_ok = dot.is_some_and(|d| d > 0 && d + 1 < domain.len());
            // trim a trailing dot from the domain (sentence punctuation)
            let mut end = e;
            while end > i + 1 && b[end - 1] == b'.' {
                end -= 1;
            }
            if local_ok && tld_ok && end > i + 1 {
                out.push(Detection {
                    kind: PiiKind::Email,
                    start: s,
                    end,
                    text: text[s..end].to_string(),
                });
            }
            i = e.max(i + 1);
        } else {
            i += 1;
        }
    }
    out
}

fn scan_ssn(text: &str, b: &[u8]) -> Vec<Detection> {
    // ###-##-#### with hyphens, not embedded in a longer digit/word run.
    let mut out = Vec::new();
    let n = b.len();
    let mut i = 0;
    while i + 11 <= n {
        let w = &b[i..i + 11];
        let shape = w[0].is_ascii_digit()
            && w[1].is_ascii_digit()
            && w[2].is_ascii_digit()
            && w[3] == b'-'
            && w[4].is_ascii_digit()
            && w[5].is_ascii_digit()
            && w[6] == b'-'
            && w[7].is_ascii_digit()
            && w[8].is_ascii_digit()
            && w[9].is_ascii_digit()
            && w[10].is_ascii_digit();
        let left_ok = i == 0 || !b[i - 1].is_ascii_digit();
        let right_ok = i + 11 >= n || !b[i + 11].is_ascii_digit();
        if shape && left_ok && right_ok {
            out.push(Detection {
                kind: PiiKind::Ssn,
                start: i,
                end: i + 11,
                text: text[i..i + 11].to_string(),
            });
            i += 11;
        } else {
            i += 1;
        }
    }
    out
}

fn scan_ipv4(text: &str, b: &[u8]) -> Vec<Detection> {
    let mut out = Vec::new();
    for &(s, e) in &runs_with_dots(b) {
        let span = &text[s..e];
        let parts: Vec<&str> = span.split('.').collect();
        if parts.len() == 4
            && parts.iter().all(|p| {
                !p.is_empty()
                    && p.len() <= 3
                    && p.bytes().all(|c| c.is_ascii_digit())
                    && p.parse::<u16>().is_ok_and(|v| v <= 255)
            })
        {
            out.push(Detection {
                kind: PiiKind::IpV4,
                start: s,
                end: e,
                text: span.to_string(),
            });
        }
    }
    out
}

/// Maximal runs of digits-and-dots (candidate IPv4 spans), not bordered by
/// alphanumerics.
fn runs_with_dots(b: &[u8]) -> Vec<(usize, usize)> {
    let mut runs = Vec::new();
    let n = b.len();
    let mut i = 0;
    while i < n {
        if b[i].is_ascii_digit() {
            let s = i;
            while i < n && (b[i].is_ascii_digit() || b[i] == b'.') {
                i += 1;
            }
            // trim trailing dots
            let mut e = i;
            while e > s && b[e - 1] == b'.' {
                e -= 1;
            }
            let left_ok = s == 0 || !b[s - 1].is_ascii_alphanumeric();
            let right_ok = e >= n || !b[e].is_ascii_alphanumeric();
            if left_ok && right_ok {
                runs.push((s, e));
            }
        } else {
            i += 1;
        }
    }
    runs
}

fn scan_credit_card(text: &str, b: &[u8]) -> Vec<Detection> {
    // candidate: runs of digits possibly grouped by single spaces or hyphens,
    // 13..=19 digits total, passing Luhn.
    let mut out = Vec::new();
    let n = b.len();
    let mut i = 0;
    while i < n {
        if b[i].is_ascii_digit() {
            // expand a group sequence: digits, with single ' '/'-' separators.
            let s = i;
            let mut e = i;
            let mut digits = 0usize;
            while e < n {
                if b[e].is_ascii_digit() {
                    digits += 1;
                    e += 1;
                } else if (b[e] == b' ' || b[e] == b'-') && e + 1 < n && b[e + 1].is_ascii_digit() {
                    e += 1;
                } else {
                    break;
                }
            }
            let left_ok = s == 0 || !b[s - 1].is_ascii_alphanumeric();
            let right_ok = e >= n || !b[e].is_ascii_alphanumeric();
            if (13..=19).contains(&digits) && left_ok && right_ok && luhn_ok(&text[s..e]) {
                out.push(Detection {
                    kind: PiiKind::CreditCard,
                    start: s,
                    end: e,
                    text: text[s..e].to_string(),
                });
            }
            i = e.max(i + 1);
        } else {
            i += 1;
        }
    }
    out
}

/// Luhn checksum over the digits of `s` (non-digits ignored).
fn luhn_ok(s: &str) -> bool {
    let digits: Vec<u32> = s
        .bytes()
        .filter(|c| c.is_ascii_digit())
        .map(|c| (c - b'0') as u32)
        .collect();
    if digits.len() < 13 {
        return false;
    }
    let mut sum = 0u32;
    let mut double = false;
    for &d in digits.iter().rev() {
        let mut v = d;
        if double {
            v *= 2;
            if v > 9 {
                v -= 9;
            }
        }
        sum += v;
        double = !double;
    }
    sum % 10 == 0
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn detects_email() {
        let dets = detect("contact me at jane.doe+test@example.co.uk please");
        assert_eq!(dets.len(), 1);
        assert_eq!(dets[0].kind, PiiKind::Email);
        assert_eq!(dets[0].text, "jane.doe+test@example.co.uk");
    }

    #[test]
    fn email_trailing_dot_trimmed() {
        let dets = detect("write to bob@mail.com.");
        assert_eq!(dets[0].text, "bob@mail.com");
    }

    #[test]
    fn detects_ssn() {
        let dets = detect("SSN: 123-45-6789.");
        assert_eq!(dets.len(), 1);
        assert_eq!(dets[0].kind, PiiKind::Ssn);
        assert_eq!(dets[0].text, "123-45-6789");
    }

    #[test]
    fn detects_ipv4_and_rejects_out_of_range() {
        let dets = detect("server at 192.168.1.100 and bogus 999.1.1.1");
        let ips: Vec<&str> = dets
            .iter()
            .filter(|d| d.kind == PiiKind::IpV4)
            .map(|d| d.text.as_str())
            .collect();
        assert_eq!(ips, vec!["192.168.1.100"]);
    }

    #[test]
    fn detects_credit_card_with_luhn() {
        // 4111 1111 1111 1111 is the classic Luhn-valid test Visa number
        let dets = detect("card 4111 1111 1111 1111 on file");
        let cards: Vec<&str> = dets
            .iter()
            .filter(|d| d.kind == PiiKind::CreditCard)
            .map(|d| d.text.as_str())
            .collect();
        assert_eq!(cards, vec!["4111 1111 1111 1111"]);
    }

    #[test]
    fn rejects_non_luhn_digit_run() {
        // 16 digits that fail Luhn → not a card
        let dets = detect("order number 1234567812345670000");
        assert!(!dets.iter().any(|d| d.kind == PiiKind::CreditCard));
    }

    #[test]
    fn redact_replaces_with_tags() {
        let text = "email a@b.com ip 10.0.0.1 ssn 111-22-3333";
        let red = redact(text);
        assert_eq!(red, "email [EMAIL] ip [IP] ssn [SSN]");
        assert!(!contains_pii(&red));
    }

    #[test]
    fn redact_with_custom_replacement() {
        let red = redact_with("mail x@y.com", |k| format!("<{k:?}>"));
        assert_eq!(red, "mail <Email>");
    }

    #[test]
    fn clean_text_has_no_pii() {
        assert!(!contains_pii("the quick brown fox jumps over the lazy dog"));
        assert!(
            detect("version 1.2.3 build 456")
                .iter()
                .all(|d| d.kind != PiiKind::IpV4)
        );
    }

    #[test]
    fn multiple_and_sorted_no_overlap() {
        let text = "a@b.com then 1.2.3.4";
        let dets = detect(text);
        assert_eq!(dets.len(), 2);
        assert!(dets[0].start < dets[1].start);
        // spans don't overlap
        assert!(dets[0].end <= dets[1].start);
    }

    #[test]
    fn serde_round_trip() {
        let dets = detect("a@b.com");
        let j = serde_json::to_string(&dets).unwrap();
        let back: Vec<Detection> = serde_json::from_str(&j).unwrap();
        assert_eq!(dets, back);
    }
}
