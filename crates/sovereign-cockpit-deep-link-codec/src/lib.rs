//! `sovereign-cockpit-deep-link-codec` — URL deep-link encoding.
//!
//! A `DeepLink` consists of a `route` path (e.g. "/feed") and a set
//! of `params` (`key=value`). `encode(link)` returns a string of the
//! form `/<route>?k1=v1&k2=v2&...` with keys sorted alphabetically
//! for stable output. Reserved characters (`=`, `&`, `?`, `%`, ` `,
//! and the byte set used by ASCII control characters) in keys and
//! values are %-encoded; decode performs the inverse.
//!
//! This is a deliberately small URL-encoding subset — no fragments,
//! no schemes — appropriate for cockpit in-app deep links. It
//! refuses to encode keys with empty names.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A deep link.
#[derive(Debug, Clone, Default, Serialize, Deserialize, PartialEq, Eq)]
pub struct DeepLink {
    /// Route path (always rendered with leading `/`).
    pub route: String,
    /// Query params (alphabetical when encoded).
    pub params: BTreeMap<String, String>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum LinkError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty key.
    #[error("param key empty")]
    EmptyKey,
    /// Malformed URL.
    #[error("malformed url: {0}")]
    Malformed(String),
    /// Bad %-encoding.
    #[error("bad %-encoding at byte {0}")]
    BadEncoding(usize),
}

fn needs_encoding(b: u8) -> bool {
    // Unreserved set per RFC 3986 plus `/`, `-`, `.`, `_`, `~`.
    !(b.is_ascii_alphanumeric() || matches!(b, b'-' | b'.' | b'_' | b'~'))
}

fn percent_encode(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for b in s.bytes() {
        if needs_encoding(b) {
            out.push_str(&format!("%{b:02X}"));
        } else {
            out.push(b as char);
        }
    }
    out
}

fn percent_decode(s: &str) -> Result<String, LinkError> {
    let bytes = s.as_bytes();
    let mut out = Vec::with_capacity(bytes.len());
    let mut i = 0;
    while i < bytes.len() {
        let b = bytes[i];
        if b == b'%' {
            if i + 2 >= bytes.len() {
                return Err(LinkError::BadEncoding(i));
            }
            let hi = (bytes[i+1] as char).to_digit(16).ok_or(LinkError::BadEncoding(i))?;
            let lo = (bytes[i+2] as char).to_digit(16).ok_or(LinkError::BadEncoding(i))?;
            out.push(((hi << 4) | lo) as u8);
            i += 3;
        } else {
            out.push(b);
            i += 1;
        }
    }
    String::from_utf8(out).map_err(|_| LinkError::Malformed("non-utf8 after decode".into()))
}

/// Encode.
pub fn encode(link: &DeepLink) -> Result<String, LinkError> {
    for k in link.params.keys() {
        if k.is_empty() { return Err(LinkError::EmptyKey); }
    }
    let mut s = String::from("/");
    let trimmed = link.route.trim_start_matches('/');
    if !trimmed.is_empty() {
        for (idx, seg) in trimmed.split('/').enumerate() {
            if idx > 0 { s.push('/'); }
            s.push_str(&percent_encode(seg));
        }
    }
    if !link.params.is_empty() {
        s.push('?');
        let mut first = true;
        for (k, v) in &link.params {
            if !first { s.push('&'); }
            first = false;
            s.push_str(&percent_encode(k));
            s.push('=');
            s.push_str(&percent_encode(v));
        }
    }
    Ok(s)
}

/// Decode.
pub fn decode(s: &str) -> Result<DeepLink, LinkError> {
    if s.is_empty() { return Err(LinkError::Malformed("empty input".into())); }
    let (path, query) = match s.find('?') {
        Some(i) => (&s[..i], Some(&s[i+1..])),
        None => (s, None),
    };
    let route_decoded: String = if let Some(rest) = path.strip_prefix('/') {
        // Decode each segment then rejoin.
        let mut out = String::from("/");
        for (idx, seg) in rest.split('/').enumerate() {
            if idx > 0 { out.push('/'); }
            out.push_str(&percent_decode(seg)?);
        }
        out
    } else {
        return Err(LinkError::Malformed("route missing leading /".into()));
    };
    let mut params = BTreeMap::new();
    if let Some(q) = query {
        if !q.is_empty() {
            for pair in q.split('&') {
                let mut it = pair.splitn(2, '=');
                let k = it.next().ok_or_else(|| LinkError::Malformed("missing key".into()))?;
                let v = it.next().unwrap_or("");
                let dk = percent_decode(k)?;
                let dv = percent_decode(v)?;
                if dk.is_empty() { return Err(LinkError::EmptyKey); }
                params.insert(dk, dv);
            }
        }
    }
    Ok(DeepLink { route: route_decoded, params })
}

/// State holder for `schema_version` + the link.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct DeepLinkCodec {
    /// Schema version.
    pub schema_version: String,
}

impl DeepLinkCodec {
    /// New.
    pub fn new() -> Self {
        Self { schema_version: SCHEMA_VERSION.into() }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), LinkError> {
        if self.schema_version != SCHEMA_VERSION { return Err(LinkError::SchemaMismatch); }
        Ok(())
    }
}

impl Default for DeepLinkCodec {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn encode_simple() {
        let mut link = DeepLink::default();
        link.route = "/feed".into();
        link.params.insert("tab".into(), "recent".into());
        assert_eq!(encode(&link).unwrap(), "/feed?tab=recent");
    }

    #[test]
    fn encode_keys_alphabetical() {
        let mut link = DeepLink::default();
        link.route = "/x".into();
        link.params.insert("z".into(), "1".into());
        link.params.insert("a".into(), "2".into());
        assert_eq!(encode(&link).unwrap(), "/x?a=2&z=1");
    }

    #[test]
    fn encode_special_chars() {
        let mut link = DeepLink::default();
        link.route = "/feed".into();
        link.params.insert("q".into(), "hello world!".into());
        let s = encode(&link).unwrap();
        assert_eq!(s, "/feed?q=hello%20world%21");
    }

    #[test]
    fn decode_simple() {
        let l = decode("/feed?tab=recent").unwrap();
        assert_eq!(l.route, "/feed");
        assert_eq!(l.params["tab"], "recent");
    }

    #[test]
    fn round_trip() {
        let mut link = DeepLink::default();
        link.route = "/users/123".into();
        link.params.insert("filter".into(), "active=true&pinned".into());
        let s = encode(&link).unwrap();
        let back = decode(&s).unwrap();
        assert_eq!(link, back);
    }

    #[test]
    fn decode_no_query() {
        let l = decode("/just/a/path").unwrap();
        assert_eq!(l.route, "/just/a/path");
        assert!(l.params.is_empty());
    }

    #[test]
    fn empty_value_ok() {
        let l = decode("/x?k=").unwrap();
        assert_eq!(l.params["k"], "");
    }

    #[test]
    fn empty_key_rejected_on_encode() {
        let mut link = DeepLink::default();
        link.route = "/x".into();
        link.params.insert("".into(), "v".into());
        assert!(matches!(encode(&link).unwrap_err(), LinkError::EmptyKey));
    }

    #[test]
    fn malformed_url_rejected() {
        assert!(matches!(decode("").unwrap_err(), LinkError::Malformed(_)));
        assert!(matches!(decode("no-leading-slash").unwrap_err(), LinkError::Malformed(_)));
    }

    #[test]
    fn bad_percent_encoding_rejected() {
        assert!(matches!(decode("/x?k=%ZZ").unwrap_err(), LinkError::BadEncoding(_)));
        assert!(matches!(decode("/x?k=%").unwrap_err(), LinkError::BadEncoding(_)));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut c = DeepLinkCodec::new();
        c.schema_version = "9.9.9".into();
        assert!(matches!(c.validate().unwrap_err(), LinkError::SchemaMismatch));
    }

    #[test]
    fn link_serde_roundtrip() {
        let mut link = DeepLink::default();
        link.route = "/x".into();
        link.params.insert("k".into(), "v".into());
        let j = serde_json::to_string(&link).unwrap();
        let back: DeepLink = serde_json::from_str(&j).unwrap();
        assert_eq!(link, back);
    }
}
