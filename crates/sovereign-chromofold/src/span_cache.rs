//! `span_cache` — FM-index-backed **span recovery** over a prompt/completion cache
//! (SDD-400's headline compressed-domain workload).
//!
//! A [`SpanCache`] holds a set of cached token-stream *entries* (prompts,
//! completions, documents — whatever the caller feeds it) as one FM-index, and
//! answers the reuse question: **"what is the longest run at the end of this new
//! query that I have already cached, and where?"** — returning the length plus
//! the *entry* and *offset* it was found at, so a caller can reuse that entry's
//! computed state (KV, embedding, …) instead of recomputing.
//!
//! Entries are joined by a reserved separator ([`u32::MAX`], assumed absent from
//! real token ids) so a recovered span never straddles two entries — every hit
//! resolves cleanly to a single `(entry, offset)`. It is the fixed-corpus case
//! where the FM-index wins: build once, recover many. CPU, no GPU (provenance-B);
//! rebuild when the cache set changes (the BWT is static).

use crate::FmIndex;

/// The separator token joining cache entries — reserved, assumed absent from real
/// token ids (vocabularies do not reach `u32::MAX`), so no recovered span crosses
/// an entry boundary.
const SEP: u32 = u32::MAX;

/// A recovered span: `len` tokens of the query's suffix were found at `offset`
/// within cache `entry`.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct SpanHit {
    /// Number of matched tokens (the longest cached suffix of the query).
    pub len: usize,
    /// Index of the cache entry the span was found in.
    pub entry: usize,
    /// Token offset within that entry where the span begins.
    pub offset: usize,
}

/// An FM-index over a set of cached token-stream entries, for span recovery.
#[derive(Debug, Clone)]
pub struct SpanCache {
    fm: FmIndex,
    /// `starts[i]` = position of entry `i` in the separator-joined corpus.
    starts: Vec<usize>,
}

impl SpanCache {
    /// Build a cache over `entries` (each a token-id stream). Entries are joined
    /// by a reserved separator so spans cannot cross boundaries.
    #[must_use]
    pub fn build(entries: &[Vec<u32>]) -> Self {
        let mut corpus: Vec<u32> = Vec::new();
        let mut starts = Vec::with_capacity(entries.len());
        for (i, e) in entries.iter().enumerate() {
            if i > 0 {
                corpus.push(SEP);
            }
            starts.push(corpus.len());
            corpus.extend_from_slice(e);
        }
        Self {
            fm: FmIndex::build(&corpus),
            starts,
        }
    }

    /// Number of cached entries.
    #[must_use]
    pub fn num_entries(&self) -> usize {
        self.starts.len()
    }

    /// Whether the cache holds no entries.
    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.starts.is_empty()
    }

    /// The longest suffix of `query` already present in some cached entry, resolved
    /// to `(len, entry, offset)` — the earliest such location (lowest entry, then
    /// lowest offset). `None` when not even the last query token is cached.
    #[must_use]
    pub fn longest_cached_span(&self, query: &[u32]) -> Option<SpanHit> {
        let (len, positions) = self.fm.longest_matching_span(query);
        if len == 0 {
            return None;
        }
        // positions are corpus-position-sorted; the first is the earliest entry+offset.
        let p = *positions.first()?;
        let entry = self.entry_of(p);
        let offset = p - self.starts[entry];
        Some(SpanHit { len, entry, offset })
    }

    /// The cache entry containing corpus position `pos` (the last entry whose start
    /// is `<= pos`). A recovered span never crosses a separator, so `pos` lands
    /// inside exactly one entry.
    fn entry_of(&self, pos: usize) -> usize {
        match self.starts.binary_search(&pos) {
            Ok(i) => i,
            Err(i) => i - 1, // starts[0] == 0 <= pos, so i >= 1 here
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // naive oracle: longest suffix of query in a single entry, earliest entry+offset.
    fn naive(entries: &[Vec<u32>], query: &[u32]) -> Option<(usize, usize, usize)> {
        for len in (1..=query.len()).rev() {
            let suffix = &query[query.len() - len..];
            for (ei, e) in entries.iter().enumerate() {
                if len <= e.len() {
                    for off in 0..=e.len() - len {
                        if &e[off..off + len] == suffix {
                            return Some((len, ei, off));
                        }
                    }
                }
            }
        }
        None
    }

    #[test]
    fn resolves_span_to_entry_and_offset() {
        let entries = vec![vec![1u32, 2, 3], vec![9, 1, 2, 3, 4], vec![5, 5]];
        let cache = SpanCache::build(&entries);
        // query ending in "2 3": longest cached suffix is "2 3" (len 2), earliest at
        // entry 0 offset 1.
        let hit = cache.longest_cached_span(&[7, 2, 3]).unwrap();
        assert_eq!(
            hit,
            SpanHit {
                len: 2,
                entry: 0,
                offset: 1
            }
        );
        // "1 2 3" (len 3): entry 0 offset 0 is earliest.
        let hit = cache.longest_cached_span(&[8, 1, 2, 3]).unwrap();
        assert_eq!(
            hit,
            SpanHit {
                len: 3,
                entry: 0,
                offset: 0
            }
        );
        // nothing cached ends the query.
        assert!(cache.longest_cached_span(&[42, 43]).is_none());
        assert_eq!(cache.num_entries(), 3);
    }

    #[test]
    fn spans_never_cross_entry_boundaries() {
        // "3" ends entry 0, "9" starts entry 1. The concatenation "3 9" spans the
        // boundary, so it must NOT match as a length-2 span — only the last token
        // "9" (len 1, entry 1) is recovered.
        let entries = vec![vec![1u32, 2, 3], vec![9, 8, 7]];
        let cache = SpanCache::build(&entries);
        let hit = cache.longest_cached_span(&[3, 9]).unwrap();
        assert_eq!(
            hit,
            SpanHit {
                len: 1,
                entry: 1,
                offset: 0
            }
        ); // just "9", not "3 9"
        // each side alone recovers within its own entry.
        assert_eq!(
            cache.longest_cached_span(&[0, 3]).unwrap(),
            SpanHit {
                len: 1,
                entry: 0,
                offset: 2
            }
        );
        assert_eq!(
            cache.longest_cached_span(&[9, 8]).unwrap(),
            SpanHit {
                len: 2,
                entry: 1,
                offset: 0
            }
        );
    }

    #[test]
    fn matches_naive_over_randomized_caches() {
        let mut state: u64 = 0x51ed270b7c3e9a14;
        let mut next = |m: u64| {
            state = state
                .wrapping_mul(6364136223846793005)
                .wrapping_add(1442695040888963407);
            (state >> 33) % m
        };
        for _ in 0..250 {
            let sigma = (next(4) + 1) as u32;
            let n_entries = (next(4) + 1) as usize;
            let entries: Vec<Vec<u32>> = (0..n_entries)
                .map(|_| {
                    (0..(next(8) + 1))
                        .map(|_| next(sigma as u64) as u32)
                        .collect()
                })
                .collect();
            let cache = SpanCache::build(&entries);
            for _ in 0..15 {
                let q: Vec<u32> = (0..(next(7) + 1))
                    .map(|_| next(sigma as u64 + 1) as u32)
                    .collect();
                let got = cache
                    .longest_cached_span(&q)
                    .map(|h| (h.len, h.entry, h.offset));
                assert_eq!(got, naive(&entries, &q), "entries={entries:?} q={q:?}");
            }
        }
    }

    #[test]
    fn empty_and_single_entry_edges() {
        assert!(SpanCache::build(&[]).longest_cached_span(&[1]).is_none());
        assert!(SpanCache::build(&[]).is_empty());
        let one = SpanCache::build(&[vec![1, 2, 1, 2]]);
        assert_eq!(
            one.longest_cached_span(&[9, 1, 2]).unwrap(),
            SpanHit {
                len: 2,
                entry: 0,
                offset: 0
            }
        );
    }
}
