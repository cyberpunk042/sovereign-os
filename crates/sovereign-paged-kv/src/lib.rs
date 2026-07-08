//! `sovereign-paged-kv` — KV-cache memory without the fragmentation.
//!
//! A transformer's key/value cache grows one token at a time, and a server runs
//! many sequences of unpredictable length at once. Reserving a contiguous
//! max-length buffer per sequence wastes most of the memory; growing contiguous
//! buffers fragments it. **PagedAttention** (vLLM) solves this the way an
//! operating system handles RAM: carve the KV memory into fixed-size **blocks**,
//! give each sequence a **page table** mapping its logical token positions to
//! physical blocks, and allocate a new block only when the current one fills.
//! Memory is then used in block-sized granules with almost no waste, and
//! sequences need not be contiguous.
//!
//! This crate is that allocator. [`PagedKvCache::append`] grows a sequence,
//! pulling blocks from a free pool as token positions cross block boundaries.
//! [`PagedKvCache::fork`] implements **copy-on-write** prefix sharing: a forked
//! sequence references its parent's blocks (bumping their reference counts)
//! instead of copying them, so two requests with a shared prompt share its KV
//! blocks until one of them writes past the boundary. [`PagedKvCache::free`]
//! releases a sequence, decrementing the shared blocks' counts and returning to
//! the pool only those that reach zero. Running out of blocks is a typed error,
//! not a panic — the signal a scheduler uses to apply back-pressure or preempt.
//!
//! [`PagedKvCache::block_for`] resolves a sequence's logical token position to its
//! `(physical_block, offset)`, the address an attention kernel would read.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use thiserror::Error;

/// Schema version of the paged-kv surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Errors from the allocator.
#[derive(Debug, Clone, PartialEq, Eq, Error)]
pub enum PagedKvError {
    /// No free blocks remain to satisfy an allocation.
    #[error("out of KV blocks (needed {needed}, free {free})")]
    OutOfMemory {
        /// Blocks requested.
        needed: usize,
        /// Blocks available.
        free: usize,
    },
    /// The referenced sequence id is unknown.
    #[error("unknown sequence {0}")]
    UnknownSequence(usize),
    /// A token position was out of the sequence's range.
    #[error("position {pos} out of range for sequence of length {len}")]
    OutOfRange {
        /// Requested position.
        pos: usize,
        /// Sequence length.
        len: usize,
    },
}

/// Per-sequence state: its physical blocks (in logical order) and token length.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
struct Sequence {
    blocks: Vec<usize>,
    len: usize,
}

/// A paged KV-cache allocator.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct PagedKvCache {
    block_size: usize,
    /// reference count per physical block (0 = free).
    refcounts: Vec<u32>,
    free: Vec<usize>,
    sequences: HashMap<usize, Sequence>,
    next_seq_id: usize,
}

impl PagedKvCache {
    /// A cache of `num_blocks` blocks, each holding `block_size` token slots.
    ///
    /// # Panics
    /// Panics if `block_size == 0`.
    pub fn new(num_blocks: usize, block_size: usize) -> Self {
        assert!(block_size > 0, "block_size must be > 0");
        Self {
            block_size,
            refcounts: vec![0; num_blocks],
            free: (0..num_blocks).rev().collect(), // pop() yields low ids first
            sequences: HashMap::new(),
            next_seq_id: 0,
        }
    }

    /// The block size (token slots per block).
    pub fn block_size(&self) -> usize {
        self.block_size
    }

    /// The number of currently-free blocks.
    pub fn num_free_blocks(&self) -> usize {
        self.free.len()
    }

    /// The total number of blocks.
    pub fn total_blocks(&self) -> usize {
        self.refcounts.len()
    }

    /// Fraction of blocks currently allocated (in `[0, 1]`).
    pub fn utilization(&self) -> f64 {
        let total = self.refcounts.len();
        if total == 0 {
            0.0
        } else {
            (total - self.free.len()) as f64 / total as f64
        }
    }

    /// Create a new, empty sequence and return its id.
    pub fn new_sequence(&mut self) -> usize {
        let id = self.next_seq_id;
        self.next_seq_id += 1;
        self.sequences.insert(
            id,
            Sequence {
                blocks: Vec::new(),
                len: 0,
            },
        );
        id
    }

    /// The token length of a sequence.
    pub fn sequence_len(&self, seq: usize) -> Option<usize> {
        self.sequences.get(&seq).map(|s| s.len)
    }

    /// How many blocks would be needed to hold `len` tokens.
    fn blocks_needed(&self, len: usize) -> usize {
        len.div_ceil(self.block_size)
    }

    fn pop_free(&mut self) -> Option<usize> {
        let b = self.free.pop()?;
        self.refcounts[b] = 1;
        Some(b)
    }

    /// Append `count` tokens to `seq`, allocating blocks as needed. A block shared
    /// via copy-on-write is duplicated before being written past (so a fork's
    /// growth doesn't corrupt the parent).
    pub fn append(&mut self, seq: usize, count: usize) -> Result<(), PagedKvError> {
        if !self.sequences.contains_key(&seq) {
            return Err(PagedKvError::UnknownSequence(seq));
        }
        let cur_len = self.sequences[&seq].len;
        let new_len = cur_len + count;
        let have = self.sequences[&seq].blocks.len();
        let need = self.blocks_needed(new_len);

        // If the last block is shared (refcount > 1) and we will write into it,
        // copy it first (copy-on-write).
        if have > 0 && cur_len % self.block_size != 0 {
            let last = *self.sequences[&seq].blocks.last().unwrap();
            if self.refcounts[last] > 1 {
                let fresh = self.pop_free().ok_or(PagedKvError::OutOfMemory {
                    needed: 1,
                    free: self.free.len(),
                })?;
                self.refcounts[last] -= 1;
                let s = self.sequences.get_mut(&seq).unwrap();
                *s.blocks.last_mut().unwrap() = fresh;
            }
        }

        let extra = need.saturating_sub(have);
        if extra > self.free.len() {
            return Err(PagedKvError::OutOfMemory {
                needed: extra,
                free: self.free.len(),
            });
        }
        for _ in 0..extra {
            let b = self.pop_free().unwrap();
            self.sequences.get_mut(&seq).unwrap().blocks.push(b);
        }
        self.sequences.get_mut(&seq).unwrap().len = new_len;
        Ok(())
    }

    /// Fork `seq` into a new sequence that shares its blocks copy-on-write.
    /// Returns the new sequence id. The shared blocks' reference counts are
    /// incremented; neither sequence pays for the shared prefix until it grows.
    pub fn fork(&mut self, seq: usize) -> Result<usize, PagedKvError> {
        let parent = self
            .sequences
            .get(&seq)
            .ok_or(PagedKvError::UnknownSequence(seq))?
            .clone();
        for &b in &parent.blocks {
            self.refcounts[b] += 1;
        }
        let id = self.next_seq_id;
        self.next_seq_id += 1;
        self.sequences.insert(id, parent);
        Ok(id)
    }

    /// Free a sequence, releasing blocks whose reference count reaches zero.
    pub fn free(&mut self, seq: usize) -> Result<(), PagedKvError> {
        let s = self
            .sequences
            .remove(&seq)
            .ok_or(PagedKvError::UnknownSequence(seq))?;
        for &b in &s.blocks {
            self.refcounts[b] -= 1;
            if self.refcounts[b] == 0 {
                self.free.push(b);
            }
        }
        Ok(())
    }

    /// Resolve logical token position `pos` of `seq` to `(physical_block, offset)`.
    pub fn block_for(&self, seq: usize, pos: usize) -> Result<(usize, usize), PagedKvError> {
        let s = self
            .sequences
            .get(&seq)
            .ok_or(PagedKvError::UnknownSequence(seq))?;
        if pos >= s.len {
            return Err(PagedKvError::OutOfRange { pos, len: s.len });
        }
        let block_idx = pos / self.block_size;
        let offset = pos % self.block_size;
        Ok((s.blocks[block_idx], offset))
    }

    /// The physical blocks a sequence currently holds (logical order).
    pub fn blocks_of(&self, seq: usize) -> Option<&[usize]> {
        self.sequences.get(&seq).map(|s| s.blocks.as_slice())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn append_allocates_blocks_on_boundary() {
        let mut c = PagedKvCache::new(10, 4); // 10 blocks of 4 tokens
        let s = c.new_sequence();
        c.append(s, 3).unwrap(); // 3 tokens → 1 block
        assert_eq!(c.blocks_of(s).unwrap().len(), 1);
        assert_eq!(c.num_free_blocks(), 9);
        c.append(s, 2).unwrap(); // now 5 tokens → 2 blocks
        assert_eq!(c.blocks_of(s).unwrap().len(), 2);
        assert_eq!(c.sequence_len(s), Some(5));
    }

    #[test]
    fn block_for_resolves_positions() {
        let mut c = PagedKvCache::new(10, 4);
        let s = c.new_sequence();
        c.append(s, 6).unwrap(); // 2 blocks
        let blocks = c.blocks_of(s).unwrap().to_vec();
        // position 0 → (block0, 0); position 5 → (block1, 1)
        assert_eq!(c.block_for(s, 0).unwrap(), (blocks[0], 0));
        assert_eq!(c.block_for(s, 5).unwrap(), (blocks[1], 1));
        assert!(matches!(
            c.block_for(s, 6),
            Err(PagedKvError::OutOfRange { .. })
        ));
    }

    #[test]
    fn fork_shares_blocks_copy_on_write() {
        let mut c = PagedKvCache::new(10, 4);
        let parent = c.new_sequence();
        c.append(parent, 8).unwrap(); // 2 blocks
        let free_before = c.num_free_blocks();
        let child = c.fork(parent).unwrap();
        // fork copies no blocks → free count unchanged
        assert_eq!(c.num_free_blocks(), free_before);
        // both see the same physical blocks
        assert_eq!(c.blocks_of(parent), c.blocks_of(child));
    }

    #[test]
    fn cow_duplicates_on_write_into_shared_block() {
        let mut c = PagedKvCache::new(10, 4);
        let parent = c.new_sequence();
        c.append(parent, 2).unwrap(); // 1 block, half full (refcount 1)
        let child = c.fork(parent).unwrap(); // shares that block (refcount 2)
        let shared_block = c.blocks_of(parent).unwrap()[0];
        // child appends into the shared, partially-full block → must copy first
        c.append(child, 1).unwrap();
        let child_block = c.blocks_of(child).unwrap()[0];
        assert_ne!(
            child_block, shared_block,
            "child should have copied the block"
        );
        // parent's block is untouched and now solely owned
        assert_eq!(c.blocks_of(parent).unwrap()[0], shared_block);
    }

    #[test]
    fn free_returns_blocks_to_pool() {
        let mut c = PagedKvCache::new(5, 4);
        let s = c.new_sequence();
        c.append(s, 12).unwrap(); // 3 blocks
        assert_eq!(c.num_free_blocks(), 2);
        c.free(s).unwrap();
        assert_eq!(c.num_free_blocks(), 5);
        assert!(matches!(c.free(s), Err(PagedKvError::UnknownSequence(_))));
    }

    #[test]
    fn free_respects_shared_refcounts() {
        let mut c = PagedKvCache::new(10, 4);
        let parent = c.new_sequence();
        c.append(parent, 8).unwrap(); // 2 blocks
        let child = c.fork(parent).unwrap();
        let free_after_fork = c.num_free_blocks();
        // freeing the child must NOT free the still-shared blocks
        c.free(child).unwrap();
        assert_eq!(c.num_free_blocks(), free_after_fork);
        // freeing the parent now releases them
        c.free(parent).unwrap();
        assert_eq!(c.num_free_blocks(), 10);
    }

    #[test]
    fn out_of_memory_is_reported() {
        let mut c = PagedKvCache::new(2, 4); // only 2 blocks
        let s = c.new_sequence();
        // 12 tokens need 3 blocks, only 2 available
        let err = c.append(s, 12).unwrap_err();
        assert!(matches!(err, PagedKvError::OutOfMemory { .. }));
        // the failed append should not have consumed blocks past the budget
        assert!(c.num_free_blocks() <= 2);
    }

    #[test]
    fn utilization_tracks_allocation() {
        let mut c = PagedKvCache::new(4, 4);
        assert_eq!(c.utilization(), 0.0);
        let s = c.new_sequence();
        c.append(s, 8).unwrap(); // 2 of 4 blocks
        assert!((c.utilization() - 0.5).abs() < 1e-9);
    }

    #[test]
    fn serde_round_trip() {
        let mut c = PagedKvCache::new(8, 4);
        let s = c.new_sequence();
        c.append(s, 6).unwrap();
        let j = serde_json::to_string(&c).unwrap();
        let back: PagedKvCache = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
        assert_eq!(back.sequence_len(s), Some(6));
    }
}
