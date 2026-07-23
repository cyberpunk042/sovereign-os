//! `sovereign-secret-scan` — catch credentials before they leak.
//!
//! Credentials end up in places they shouldn't: pasted into a prompt, captured in
//! a log line, echoed in a trace. For a sovereign system that is a serious leak.
//! This crate scans text for secrets two ways.
//!
//! **Known patterns.** Many providers give their keys a recognizable shape — AWS
//! access-key ids start `AKIA` followed by 16 uppercase/digits, GitHub tokens
//! start `ghp_`/`gho_`/`ghs_`/`ghr_`, Slack bot tokens `xox[bpas]-…`, and PEM
//! private keys begin `-----BEGIN … PRIVATE KEY-----`. These are matched exactly
//! and reported with high confidence.
//!
//! **High-entropy heuristic.** Unrecognized API keys still look like keys: long
//! runs of base64/hex-ish characters with near-random bytes. The scanner flags any
//! sufficiently long token whose Shannon entropy per character exceeds a
//! threshold — catching novel formats that no pattern lists, at the cost of the
//! occasional false positive (tuned conservatively).
//!
//! [`scan`] returns typed [`Finding`]s with byte spans (known-pattern matches take
//! precedence over overlapping entropy matches); [`redact`] returns a copy with
//! each secret replaced by a tag. A guard, layered — not a vault.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the secret-scan surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// The kind of secret found.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum SecretKind {
    /// AWS access key id (`AKIA…`).
    AwsAccessKey,
    /// GitHub personal/OAuth/server/refresh token (`gh*_…`).
    GitHubToken,
    /// Slack token (`xox*-…`).
    SlackToken,
    /// A PEM private-key header.
    PrivateKey,
    /// A generic high-entropy token (possible unrecognized key).
    HighEntropy,
}

impl SecretKind {
    /// The redaction tag for this kind.
    pub fn tag(&self) -> &'static str {
        match self {
            SecretKind::AwsAccessKey => "[AWS_KEY]",
            SecretKind::GitHubToken => "[GITHUB_TOKEN]",
            SecretKind::SlackToken => "[SLACK_TOKEN]",
            SecretKind::PrivateKey => "[PRIVATE_KEY]",
            SecretKind::HighEntropy => "[SECRET]",
        }
    }
}

/// A detected secret.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Finding {
    /// What kind of secret.
    pub kind: SecretKind,
    /// Start byte offset (inclusive).
    pub start: usize,
    /// End byte offset (exclusive).
    pub end: usize,
    /// The matched text.
    pub text: String,
}

/// Minimum length for the high-entropy heuristic to consider a token.
pub const MIN_ENTROPY_TOKEN_LEN: usize = 20;
/// Shannon entropy-per-character threshold (bits) above which a long token is
/// flagged. Random base64 approaches ~6 bits/char; ordinary words are well below.
pub const ENTROPY_THRESHOLD_BITS: f64 = 4.0;

/// Scan `text` for secrets. Known-pattern matches take precedence over
/// overlapping high-entropy matches. Results are sorted by position, non-overlapping.
pub fn scan(text: &str) -> Vec<Finding> {
    let mut found = Vec::new();
    found.extend(scan_known(text));
    found.extend(scan_entropy(text));

    // known patterns first (longer/earlier wins); drop overlaps.
    found.sort_by(|a, b| {
        a.start
            .cmp(&b.start)
            .then(known_rank(&a.kind).cmp(&known_rank(&b.kind)))
            .then(b.end.cmp(&a.end))
    });
    let mut out: Vec<Finding> = Vec::new();
    let mut last_end = 0usize;
    for f in found {
        if f.start >= last_end {
            last_end = f.end;
            out.push(f);
        }
    }
    out
}

fn known_rank(k: &SecretKind) -> u8 {
    if matches!(k, SecretKind::HighEntropy) {
        1
    } else {
        0
    }
}

/// Redact `text`, replacing each secret with its `[KIND]` tag.
pub fn redact(text: &str) -> String {
    let findings = scan(text);
    let mut out = String::with_capacity(text.len());
    let mut cursor = 0usize;
    for f in &findings {
        out.push_str(&text[cursor..f.start]);
        out.push_str(f.kind.tag());
        cursor = f.end;
    }
    out.push_str(&text[cursor..]);
    out
}

/// Whether `text` contains any secret.
pub fn contains_secret(text: &str) -> bool {
    !scan(text).is_empty()
}

/// A token character for the purpose of secret scanning (key-ish charset).
///
/// `=` is deliberately excluded: it is base64 padding but mostly appears as the
/// `key=value` separator, and including it would merge a variable name onto its
/// secret value and defeat prefix matching.
fn is_token_char(c: char) -> bool {
    c.is_ascii_alphanumeric() || matches!(c, '_' | '-' | '+' | '/')
}

/// Split `text` into `(token, start_byte)` runs of token characters.
fn tokens(text: &str) -> Vec<(&str, usize)> {
    let mut out = Vec::new();
    let bytes = text.as_bytes();
    let n = bytes.len();
    let mut i = 0;
    while i < n {
        if is_token_char(bytes[i] as char) {
            let s = i;
            while i < n && is_token_char(bytes[i] as char) {
                i += 1;
            }
            out.push((&text[s..i], s));
        } else {
            i += 1;
        }
    }
    out
}

fn scan_known(text: &str) -> Vec<Finding> {
    let mut out = Vec::new();

    // PEM private key header (multi-word, scan the raw text).
    if let Some(pos) = text.find("-----BEGIN ") {
        let rest = &text[pos..];
        if rest.starts_with("-----BEGIN ")
            && rest
                .lines()
                .next()
                .is_some_and(|l| l.contains("PRIVATE KEY-----"))
        {
            let line = rest.lines().next().unwrap();
            out.push(Finding {
                kind: SecretKind::PrivateKey,
                start: pos,
                end: pos + line.len(),
                text: line.to_string(),
            });
        }
    }

    for (tok, start) in tokens(text) {
        let end = start + tok.len();
        // AWS access key: AKIA + 16 [A-Z0-9], total 20.
        if tok.len() == 20
            && tok.starts_with("AKIA")
            && tok[4..]
                .bytes()
                .all(|b| b.is_ascii_uppercase() || b.is_ascii_digit())
        {
            out.push(Finding {
                kind: SecretKind::AwsAccessKey,
                start,
                end,
                text: tok.to_string(),
            });
            continue;
        }
        // GitHub token: gh[poshr]_ + >=20 base62.
        if tok.len() >= 24
            && (tok.starts_with("ghp_")
                || tok.starts_with("gho_")
                || tok.starts_with("ghs_")
                || tok.starts_with("ghr_"))
        {
            out.push(Finding {
                kind: SecretKind::GitHubToken,
                start,
                end,
                text: tok.to_string(),
            });
            continue;
        }
        // Slack token: xoxb-/xoxp-/xoxa-/xoxs- + token body.
        if tok.len() >= 12
            && (tok.starts_with("xoxb-")
                || tok.starts_with("xoxp-")
                || tok.starts_with("xoxa-")
                || tok.starts_with("xoxs-"))
        {
            out.push(Finding {
                kind: SecretKind::SlackToken,
                start,
                end,
                text: tok.to_string(),
            });
            continue;
        }
    }
    out
}

fn scan_entropy(text: &str) -> Vec<Finding> {
    let mut out = Vec::new();
    for (tok, start) in tokens(text) {
        if tok.len() >= MIN_ENTROPY_TOKEN_LEN && shannon_entropy(tok) >= ENTROPY_THRESHOLD_BITS {
            out.push(Finding {
                kind: SecretKind::HighEntropy,
                start,
                end: start + tok.len(),
                text: tok.to_string(),
            });
        }
    }
    out
}

/// Shannon entropy (bits per character) of a string. Exposed so the token-law
/// entropy plane (`sovereign-token-law-entropy`, SDD-513) projects the SAME
/// definition of "high entropy" the post-hoc scanner uses — the plane and the
/// StreamGuard scan can never disagree on what counts as a secret-shaped run.
pub fn shannon_entropy(s: &str) -> f64 {
    use std::collections::HashMap;
    if s.is_empty() {
        return 0.0;
    }
    let mut counts: HashMap<char, usize> = HashMap::new();
    let mut total = 0usize;
    for c in s.chars() {
        *counts.entry(c).or_insert(0) += 1;
        total += 1;
    }
    let n = total as f64;
    let mut h = 0.0;
    for &c in counts.values() {
        let p = c as f64 / n;
        h -= p * p.log2();
    }
    h
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn detects_aws_access_key() {
        let f = scan("key=AKIAIOSFODNN7EXAMPLE done");
        assert!(
            f.iter()
                .any(|x| x.kind == SecretKind::AwsAccessKey && x.text == "AKIAIOSFODNN7EXAMPLE")
        );
    }

    #[test]
    fn detects_github_token() {
        let tok = "ghp_1234567890abcdefABCDEF1234567890abcd";
        let f = scan(&format!("token: {tok}"));
        assert!(
            f.iter()
                .any(|x| x.kind == SecretKind::GitHubToken && x.text == tok)
        );
    }

    #[test]
    fn detects_slack_token() {
        let tok = "xoxb-12345-67890-abcdefghij";
        let f = scan(&format!("slack {tok}"));
        assert!(f.iter().any(|x| x.kind == SecretKind::SlackToken));
    }

    #[test]
    fn detects_private_key_header() {
        let text = "-----BEGIN RSA PRIVATE KEY-----\nMIIE...";
        let f = scan(text);
        assert!(f.iter().any(|x| x.kind == SecretKind::PrivateKey));
    }

    #[test]
    fn detects_high_entropy_token() {
        // a random-looking 40-char base64 string
        let secret = "aZ3kP9qL2mX7vB1nC4dF6gH8jK0sT5wY2uE9rO3p";
        let f = scan(&format!("API_KEY={secret}"));
        assert!(
            f.iter()
                .any(|x| x.kind == SecretKind::HighEntropy && x.text == secret)
        );
    }

    #[test]
    fn ordinary_text_has_low_entropy() {
        // long but low-entropy English should not be flagged
        let text = "the meeting is scheduled for tomorrow afternoon at the office downtown";
        assert!(!contains_secret(text), "flagged: {:?}", scan(text));
    }

    #[test]
    fn short_random_strings_not_flagged() {
        // below the min length → not entropy-flagged
        assert!(!contains_secret("a1b2c3"));
    }

    #[test]
    fn redact_replaces_secrets() {
        let text = "use AKIAIOSFODNN7EXAMPLE and ghp_1234567890abcdefABCDEF1234567890abcd";
        let red = redact(text);
        assert!(red.contains("[AWS_KEY]"));
        assert!(red.contains("[GITHUB_TOKEN]"));
        assert!(!contains_secret(&red));
    }

    #[test]
    fn known_pattern_precedence_over_entropy() {
        // an AWS key is also high-entropy; it should be reported as AwsAccessKey,
        // not duplicated as HighEntropy.
        let f = scan("AKIAIOSFODNN7EXAMPLE");
        assert_eq!(f.len(), 1);
        assert_eq!(f[0].kind, SecretKind::AwsAccessKey);
    }

    #[test]
    fn entropy_values_make_sense() {
        assert!(shannon_entropy("aaaaaaaa") < 0.1); // all same char
        assert!(shannon_entropy("aZ3kP9qL2mX7vB1nC4dF") > 3.5); // varied
    }

    #[test]
    fn serde_round_trip() {
        let f = scan("AKIAIOSFODNN7EXAMPLE");
        let j = serde_json::to_string(&f).unwrap();
        let back: Vec<Finding> = serde_json::from_str(&j).unwrap();
        assert_eq!(f, back);
    }
}
