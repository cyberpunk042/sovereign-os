//! `sovereign-serve` — a cost-aware serving orchestrator.
//!
//! The cost crates each answer one question — is this cached? how hard is it?
//! can I afford it? — but a runtime needs them wired into one decision path.
//! This crate is that path. A single [`Server::serve`] call, for each request:
//!
//! 1. **Cache** — if the exact request was served before, return the cached
//!    completion for free (the literal `$0` case); the model never runs.
//! 2. **Complexity** — estimate the request's difficulty (for routing / logging).
//! 3. **Budget** — refuse *before* generating if the output would blow the
//!    token budget, so an over-budget request is rejected, not run.
//! 4. **Generate** — run the supplied model.
//! 5. **Account & cache** — record input/output tokens and cache the result.
//!
//! It is generic over the token counter and the generator, so it wraps the real
//! tokenizer and runtime in production and plain closures in tests. The cache,
//! meter, and complexity crates do the work; this composes them.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use sovereign_completion_cache::{CompletionCache, request_key};
use sovereign_complexity::{Complexity, Tier};
use sovereign_token_meter::{Budget, MeterError, TokenMeter};
use thiserror::Error;

/// Schema version of the serve surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Why a request could not be served.
#[derive(Debug, Error, PartialEq)]
pub enum ServeError {
    /// The request would exceed the token budget (checked before generating).
    #[error("budget: {0}")]
    Budget(#[from] MeterError),
    /// The generator failed.
    #[error("generate: {0}")]
    Generate(String),
}

/// The outcome of serving one request.
#[derive(Debug, Clone, PartialEq)]
pub struct ServeResult {
    /// The completion text.
    pub text: String,
    /// Whether it came from cache (and so cost nothing to produce).
    pub cache_hit: bool,
    /// The request's estimated complexity tier.
    pub tier: Tier,
    /// Input tokens charged (0 on a cache hit).
    pub input_tokens: usize,
    /// Output tokens charged (0 on a cache hit).
    pub output_tokens: usize,
}

/// A cost-aware server: a cache + a token meter.
#[derive(Debug, Clone)]
pub struct Server {
    cache: CompletionCache,
    meter: TokenMeter,
}

impl Server {
    /// A server with the given cache capacity and an unlimited budget.
    pub fn new(cache_capacity: usize) -> Self {
        Self {
            cache: CompletionCache::new(cache_capacity),
            meter: TokenMeter::new(),
        }
    }

    /// A server with a cache capacity and a token budget.
    pub fn with_budget(cache_capacity: usize, budget: Budget) -> Self {
        Self {
            cache: CompletionCache::new(cache_capacity),
            meter: TokenMeter::with_budget(budget),
        }
    }

    /// The token meter (usage + budget).
    pub fn meter(&self) -> &TokenMeter {
        &self.meter
    }

    /// Cache hit rate so far.
    pub fn cache_hit_rate(&self) -> f64 {
        self.cache.hit_rate()
    }

    /// Serve `prompt`: cache → complexity → budget → generate → account.
    ///
    /// `count_tokens` measures a string in the runtime's tokens; `generate`
    /// runs the model for `(prompt, max_new, seed)`.
    pub fn serve<C, G>(
        &mut self,
        prompt: &str,
        max_new: usize,
        seed: u64,
        count_tokens: C,
        mut generate: G,
    ) -> Result<ServeResult, ServeError>
    where
        C: Fn(&str) -> usize,
        G: FnMut(&str, usize, u64) -> Result<String, String>,
    {
        let complexity: Complexity = sovereign_complexity::estimate(prompt);
        let tier = complexity.tier();

        // 1. cache — a hit costs nothing
        let key = request_key(prompt, max_new, seed);
        if let Some(text) = self.cache.get(key) {
            return Ok(ServeResult {
                text,
                cache_hit: true,
                tier,
                input_tokens: 0,
                output_tokens: 0,
            });
        }

        // 3. budget — refuse before spending
        if !self.meter.can_spend_output(max_new) {
            // surface the precise budget error
            return Err(self
                .meter
                .clone()
                .try_spend_output(max_new)
                .unwrap_err()
                .into());
        }

        // 4. generate
        let input_tokens = count_tokens(prompt);
        let text = generate(prompt, max_new, seed).map_err(ServeError::Generate)?;
        let output_tokens = count_tokens(&text);

        // 5. account & cache
        self.meter.record_input(input_tokens);
        self.meter.record_output(output_tokens);
        self.cache.put(key, text.clone());

        Ok(ServeResult {
            text,
            cache_hit: false,
            tier,
            input_tokens,
            output_tokens,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::cell::Cell;

    // simple token counter: whitespace-separated words
    fn words(s: &str) -> usize {
        s.split_whitespace().count()
    }

    #[test]
    fn first_call_generates_then_caches() {
        let mut srv = Server::new(8);
        let calls = Cell::new(0);
        let g = |_p: &str, _m: usize, _s: u64| {
            calls.set(calls.get() + 1);
            Ok("the result here".to_string())
        };

        let r1 = srv.serve("a hard prompt", 10, 1, words, g).unwrap();
        assert!(!r1.cache_hit);
        assert_eq!(r1.output_tokens, 3); // "the result here"
        assert_eq!(calls.get(), 1);

        // identical request → cache hit, generator NOT called again
        let g2 = |_p: &str, _m: usize, _s: u64| {
            calls.set(calls.get() + 1);
            Ok("DIFFERENT".to_string())
        };
        let r2 = srv.serve("a hard prompt", 10, 1, words, g2).unwrap();
        assert!(r2.cache_hit);
        assert_eq!(r2.text, "the result here"); // served from cache
        assert_eq!(calls.get(), 1); // unchanged
        assert!(srv.cache_hit_rate() > 0.0);
    }

    #[test]
    fn budget_is_enforced_before_generating() {
        let mut srv = Server::with_budget(
            8,
            Budget {
                max_total: None,
                max_output: Some(5),
            },
        );
        let calls = Cell::new(0);
        let g = |_p: &str, _m: usize, _s: u64| {
            calls.set(calls.get() + 1);
            Ok("x".to_string())
        };
        // ask for 10 output tokens against a 5 budget → rejected, g not called
        let err = srv.serve("prompt", 10, 1, words, g).unwrap_err();
        assert!(matches!(err, ServeError::Budget(_)));
        assert_eq!(calls.get(), 0);
    }

    #[test]
    fn token_usage_accumulates_across_requests() {
        let mut srv = Server::new(8);
        let g = |_p: &str, _m: usize, _s: u64| Ok("one two".to_string());
        srv.serve("hello world", 4, 1, words, g).unwrap(); // in 2, out 2
        srv.serve("foo bar baz", 4, 2, words, g).unwrap(); // in 3, out 2
        assert_eq!(srv.meter().usage().input_tokens, 5);
        assert_eq!(srv.meter().usage().output_tokens, 4);
    }

    #[test]
    fn complexity_tier_is_reported() {
        let mut srv = Server::new(8);
        let g = |_p: &str, _m: usize, _s: u64| Ok("ok".to_string());
        let trivial = srv.serve("hi", 4, 1, words, g).unwrap();
        assert_eq!(trivial.tier, Tier::Trivial);
        let complex = srv
            .serve(
                "explain step by step and prove why, then analyze and derive the code ```fn x(){}```",
                4,
                2,
                words,
                g,
            )
            .unwrap();
        assert_eq!(complex.tier, Tier::Complex);
    }

    #[test]
    fn generate_error_propagates() {
        let mut srv = Server::new(8);
        let g = |_p: &str, _m: usize, _s: u64| Err("model died".to_string());
        assert_eq!(
            srv.serve("p", 4, 1, words, g).unwrap_err(),
            ServeError::Generate("model died".to_string())
        );
    }

    #[test]
    fn different_requests_miss_the_cache() {
        let mut srv = Server::new(8);
        let calls = Cell::new(0);
        let g = |_p: &str, _m: usize, _s: u64| {
            calls.set(calls.get() + 1);
            Ok("r".to_string())
        };
        srv.serve("prompt a", 4, 1, words, g).unwrap();
        srv.serve("prompt b", 4, 1, words, g).unwrap(); // different prompt
        srv.serve("prompt a", 4, 2, words, g).unwrap(); // different seed
        assert_eq!(calls.get(), 3); // all distinct keys
    }
}
