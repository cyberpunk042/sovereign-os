//! `sovereign-continuous-batch` — keep the model busy without running out of KV.
//!
//! Static batching waits for a whole batch to finish before starting the next, so
//! a long generation stalls every short one beside it. **Continuous batching**
//! (a.k.a. in-flight batching) instead treats each *decode step* as the unit of
//! work: every running sequence advances one token per step, a sequence that hits
//! its stop condition leaves immediately, and a waiting request is admitted into
//! the freed slot the very next step. The result is far higher GPU utilisation.
//!
//! The hard part is memory. KV blocks are finite ([`sovereign_paged_kv`]), and an
//! admitted prompt plus its growing generation consume them. This scheduler:
//! **admits** a queued request only when there are enough free blocks for its
//! prompt and a free batch slot; **decodes** all running sequences a token at a
//! time, allocating blocks on demand; and, when a decode step would run out of
//! blocks, **preempts** the most-recently-admitted running sequence — freeing its
//! blocks and returning it to the front of the queue to resume later — so the
//! system degrades gracefully instead of deadlocking.
//!
//! [`Scheduler::add_request`] queues work; [`Scheduler::step`] runs one decode
//! step and reports what was admitted, finished, and preempted. A sequence
//! finishes when it reaches its declared `max_tokens` (a stand-in for any stop
//! condition the caller checks).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use sovereign_paged_kv::PagedKvCache;
use std::collections::VecDeque;

/// Schema version of the continuous-batch surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A queued generation request.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Request {
    /// Caller-assigned id (echoed back in outcomes).
    pub id: u64,
    /// Number of prompt tokens to seat before generation.
    pub prompt_len: usize,
    /// Total tokens to generate (prompt + completion) before it finishes.
    pub max_tokens: usize,
}

/// A running sequence's bookkeeping.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
struct Running {
    request: Request,
    /// the paged-kv sequence id.
    seq: usize,
    /// tokens produced so far (starts at prompt_len once seated).
    produced: usize,
}

/// What one [`Scheduler::step`] did.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
pub struct StepOutcome {
    /// Request ids admitted (seated) this step.
    pub admitted: Vec<u64>,
    /// Request ids that finished this step.
    pub finished: Vec<u64>,
    /// Request ids preempted back to the queue this step.
    pub preempted: Vec<u64>,
    /// Number of sequences that decoded a token this step.
    pub decoded: usize,
}

/// A continuous-batching scheduler over a paged KV cache.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Scheduler {
    cache: PagedKvCache,
    max_batch: usize,
    waiting: VecDeque<Request>,
    running: Vec<Running>,
}

impl Scheduler {
    /// A scheduler over `num_blocks` KV blocks of `block_size` tokens, running at
    /// most `max_batch` sequences concurrently.
    pub fn new(num_blocks: usize, block_size: usize, max_batch: usize) -> Self {
        Self {
            cache: PagedKvCache::new(num_blocks, block_size),
            max_batch: max_batch.max(1),
            waiting: VecDeque::new(),
            running: Vec::new(),
        }
    }

    /// Queue a request.
    pub fn add_request(&mut self, request: Request) {
        self.waiting.push_back(request);
    }

    /// Number of running sequences.
    pub fn running_count(&self) -> usize {
        self.running.len()
    }

    /// Number of waiting requests.
    pub fn waiting_count(&self) -> usize {
        self.waiting.len()
    }

    /// Whether there is no work left (nothing running or waiting).
    pub fn is_idle(&self) -> bool {
        self.running.is_empty() && self.waiting.is_empty()
    }

    /// Free KV blocks remaining.
    pub fn free_blocks(&self) -> usize {
        self.cache.num_free_blocks()
    }

    /// Run one decode step: admit what fits, decode the running set a token each,
    /// preempt under memory pressure, and finish any sequence that hit its limit.
    pub fn step(&mut self) -> StepOutcome {
        let mut out = StepOutcome::default();

        // 1. admit waiting requests while there is room (batch slot + blocks).
        while self.running.len() < self.max_batch {
            let Some(req) = self.waiting.front().cloned() else {
                break;
            };
            let need = req.prompt_len.div_ceil(self.cache.block_size());
            if need > self.cache.num_free_blocks() {
                break; // not enough memory to seat this prompt right now
            }
            let seq = self.cache.new_sequence();
            // seating the prompt should succeed given the check above.
            if self.cache.append(seq, req.prompt_len).is_err() {
                // ran out unexpectedly; undo and stop admitting.
                let _ = self.cache.free(seq);
                break;
            }
            self.waiting.pop_front();
            out.admitted.push(req.id);
            self.running.push(Running {
                produced: req.prompt_len,
                request: req,
                seq,
            });
        }

        // 2. decode each running sequence one token, preempting on OOM.
        let mut i = 0;
        while i < self.running.len() {
            // a sequence at/over its limit finishes without decoding.
            if self.running[i].produced >= self.running[i].request.max_tokens {
                let r = self.running.remove(i);
                let _ = self.cache.free(r.seq);
                out.finished.push(r.request.id);
                continue;
            }
            let seq = self.running[i].seq;
            match self.cache.append(seq, 1) {
                Ok(()) => {
                    self.running[i].produced += 1;
                    out.decoded += 1;
                    if self.running[i].produced >= self.running[i].request.max_tokens {
                        let r = self.running.remove(i);
                        let _ = self.cache.free(r.seq);
                        out.finished.push(r.request.id);
                        continue;
                    }
                    i += 1;
                }
                Err(_) => {
                    // out of blocks: preempt the most-recently-admitted running
                    // sequence (highest index) back to the queue to free memory.
                    let victim_idx = self.running.len() - 1;
                    let victim = self.running.remove(victim_idx);
                    let _ = self.cache.free(victim.seq);
                    out.preempted.push(victim.request.id);
                    // requeue at the front so it resumes soon; reset to re-seat.
                    self.waiting.push_front(victim.request);
                    if victim_idx == i {
                        // we removed the very sequence we were decoding; retry the
                        // same slot (now a different sequence or end).
                        continue;
                    }
                    // otherwise retry decoding the current sequence with freed space.
                }
            }
        }
        out
    }

    /// Run steps until idle (or `max_steps`), returning the total steps taken.
    /// A safety cap prevents an infinite loop if memory can never seat a request.
    pub fn run_to_idle(&mut self, max_steps: usize) -> usize {
        let mut steps = 0;
        while !self.is_idle() && steps < max_steps {
            let before = (self.running.len(), self.waiting.len());
            self.step();
            steps += 1;
            // detect a stall (no progress possible) to avoid spinning forever.
            if self.running.is_empty() && (self.running.len(), self.waiting.len()) == before {
                break;
            }
        }
        steps
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn req(id: u64, prompt: usize, max: usize) -> Request {
        Request {
            id,
            prompt_len: prompt,
            max_tokens: max,
        }
    }

    #[test]
    fn admits_and_finishes_a_single_request() {
        let mut s = Scheduler::new(100, 4, 8);
        s.add_request(req(1, 4, 6)); // prompt 4, generate to 6 tokens total
        let mut finished = Vec::new();
        for _ in 0..10 {
            let o = s.step();
            finished.extend(o.finished);
            if s.is_idle() {
                break;
            }
        }
        assert_eq!(finished, vec![1]);
        assert!(s.is_idle());
        // all blocks returned
        assert_eq!(s.free_blocks(), 100);
    }

    #[test]
    fn batches_multiple_requests_concurrently() {
        let mut s = Scheduler::new(100, 4, 8);
        for id in 0..5 {
            s.add_request(req(id, 4, 8));
        }
        let o = s.step(); // first step admits all 5 (room), decodes them
        assert_eq!(o.admitted.len(), 5);
        assert_eq!(s.running_count(), 5);
        assert_eq!(o.decoded, 5);
    }

    #[test]
    fn respects_max_batch() {
        let mut s = Scheduler::new(1000, 4, 2); // batch cap 2
        for id in 0..5 {
            s.add_request(req(id, 4, 100));
        }
        s.step();
        assert_eq!(s.running_count(), 2);
        assert_eq!(s.waiting_count(), 3);
    }

    #[test]
    fn admission_waits_when_memory_is_tight() {
        // 2 blocks of 4 = 8 token slots. A 6-token prompt needs 2 blocks.
        let mut s = Scheduler::new(2, 4, 8);
        s.add_request(req(1, 6, 7));
        s.add_request(req(2, 4, 5));
        let o = s.step();
        // only the first can be seated (uses both blocks)
        assert_eq!(o.admitted, vec![1]);
        assert_eq!(s.waiting_count(), 1);
    }

    #[test]
    fn preempts_under_memory_pressure() {
        // tiny memory: 3 blocks of 4. Two requests each want to grow long.
        let mut s = Scheduler::new(3, 4, 8);
        s.add_request(req(1, 4, 100));
        s.add_request(req(2, 4, 100));
        // run several steps; at some point growth exhausts blocks and a preempt
        // must occur (otherwise it would deadlock).
        let mut saw_preempt = false;
        for _ in 0..50 {
            let o = s.step();
            if !o.preempted.is_empty() {
                saw_preempt = true;
                break;
            }
            if s.is_idle() {
                break;
            }
        }
        assert!(saw_preempt, "expected a preemption under memory pressure");
        // the system did not lose any request (still accounted for somewhere)
        assert!(s.running_count() + s.waiting_count() >= 1);
    }

    #[test]
    fn eventually_completes_all_under_pressure() {
        let mut s = Scheduler::new(4, 4, 4);
        for id in 0..3 {
            s.add_request(req(id, 4, 12));
        }
        let mut finished = std::collections::HashSet::new();
        for _ in 0..500 {
            let o = s.step();
            for f in o.finished {
                finished.insert(f);
            }
            if s.is_idle() {
                break;
            }
        }
        // every request finishes despite the memory pressure (preempt + resume)
        assert_eq!(finished.len(), 3, "not all finished: {finished:?}");
        assert_eq!(s.free_blocks(), 4);
    }

    #[test]
    fn idle_scheduler() {
        let mut s = Scheduler::new(10, 4, 4);
        assert!(s.is_idle());
        let o = s.step();
        assert_eq!(o, StepOutcome::default());
    }

    #[test]
    fn serde_round_trip() {
        let mut s = Scheduler::new(10, 4, 4);
        s.add_request(req(1, 4, 8));
        s.step();
        let j = serde_json::to_string(&s).unwrap();
        let back: Scheduler = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
