//! `sovereign-merkle-tree` — summarize a dataset in one hash, and find what changed.
//!
//! Two replicas hold what should be the same list of records. Are they in sync? If
//! not, which entries differ? Comparing element by element is `O(n)` every time. A
//! **Merkle tree** answers both questions far more cheaply: hash the leaves, then
//! hash pairs of hashes up to a single **root**. If two roots match, the datasets
//! are identical — one comparison. If they differ, you descend the two trees in
//! lockstep, following only the branches whose subtree hashes disagree, and reach
//! exactly the changed leaves in time proportional to the number of differences,
//! not the size of the data. That descent is the heart of anti-entropy sync.
//!
//! The tree also produces an **audit proof**: a logarithmic list of sibling hashes
//! that, folded together with a leaf, must reproduce the root — evidence that a
//! specific leaf belongs to a dataset with a known root, without revealing the rest.
//!
//! [`MerkleTree::from_leaves`] hashes byte-slice leaves; [`MerkleTree::root`] is the
//! summary; [`MerkleTree::proof`] and [`MerkleTree::verify`] handle membership
//! proofs; [`MerkleTree::diff`] returns the indices of leaves that differ from
//! another tree. Odd nodes are promoted unchanged to the next level, so the shape is
//! fully determined by the leaf count. The hash is a fast **non-cryptographic**
//! 64-bit FNV-1a with leaf/internal domain separation — built for detecting
//! accidental divergence, not for resisting a deliberate forger.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the Merkle-tree surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

const FNV_OFFSET: u64 = 0xcbf2_9ce4_8422_2325;
const FNV_PRIME: u64 = 0x0000_0100_0000_01B3;

/// FNV-1a hash of `bytes` seeded with `seed` (used for domain separation).
fn fnv1a(seed: u64, bytes: &[u8]) -> u64 {
    let mut h = seed;
    for &b in bytes {
        h ^= b as u64;
        h = h.wrapping_mul(FNV_PRIME);
    }
    h
}

/// Leaf-domain seed (distinct from the internal-node seed for domain separation).
const LEAF_SEED: u64 = FNV_OFFSET;
/// Internal-node-domain seed.
const INTERNAL_SEED: u64 = FNV_OFFSET ^ 0x01;

/// Hash of a leaf's bytes.
fn hash_leaf(data: &[u8]) -> u64 {
    fnv1a(LEAF_SEED, data)
}

/// Hash combining two child hashes (separate domain from leaves).
fn hash_internal(left: u64, right: u64) -> u64 {
    let mut buf = [0u8; 16];
    buf[..8].copy_from_slice(&left.to_le_bytes());
    buf[8..].copy_from_slice(&right.to_le_bytes());
    fnv1a(INTERNAL_SEED, &buf)
}

/// The root hash of an empty tree.
const EMPTY_ROOT: u64 = FNV_OFFSET;

/// A membership proof: the sibling hashes from a leaf up to the root.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Proof {
    /// The leaf index this proof is for.
    pub index: usize,
    /// Total leaves in the tree (fixes the tree shape).
    pub num_leaves: usize,
    /// Sibling hashes, bottom level first.
    pub siblings: Vec<u64>,
}

/// A Merkle tree over a fixed list of leaf hashes.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct MerkleTree {
    /// Levels bottom-up: `levels[0]` are the leaf hashes, the last is `[root]`.
    levels: Vec<Vec<u64>>,
    num_leaves: usize,
}

impl MerkleTree {
    /// Build a tree from leaf byte-slices.
    pub fn from_leaves<B: AsRef<[u8]>>(leaves: &[B]) -> Self {
        let leaf_hashes: Vec<u64> = leaves.iter().map(|l| hash_leaf(l.as_ref())).collect();
        Self::from_hashes(leaf_hashes)
    }

    /// Build a tree from already-computed leaf hashes.
    pub fn from_hashes(leaf_hashes: Vec<u64>) -> Self {
        let num_leaves = leaf_hashes.len();
        if num_leaves == 0 {
            return Self {
                levels: vec![vec![]],
                num_leaves: 0,
            };
        }
        let mut levels = vec![leaf_hashes];
        while levels.last().unwrap().len() > 1 {
            let cur = levels.last().unwrap();
            let mut next = Vec::with_capacity(cur.len().div_ceil(2));
            let mut i = 0;
            while i < cur.len() {
                if i + 1 < cur.len() {
                    next.push(hash_internal(cur[i], cur[i + 1]));
                    i += 2;
                } else {
                    next.push(cur[i]); // promote the lone node
                    i += 1;
                }
            }
            levels.push(next);
        }
        Self { levels, num_leaves }
    }

    /// The root hash (a fixed sentinel for an empty tree).
    pub fn root(&self) -> u64 {
        match self.levels.last() {
            Some(top) if !top.is_empty() => top[0],
            _ => EMPTY_ROOT,
        }
    }

    /// The number of leaves.
    pub fn len(&self) -> usize {
        self.num_leaves
    }
    /// Whether the tree has no leaves.
    pub fn is_empty(&self) -> bool {
        self.num_leaves == 0
    }
    /// The height (number of levels above the leaves; 0 for `<= 1` leaf).
    pub fn height(&self) -> usize {
        self.levels.len().saturating_sub(1)
    }
    /// The hash stored at `levels[0][index]`, if present.
    pub fn leaf_hash(&self, index: usize) -> Option<u64> {
        self.levels.first().and_then(|l| l.get(index)).copied()
    }

    /// Build a membership proof for the leaf at `index`.
    pub fn proof(&self, index: usize) -> Option<Proof> {
        if index >= self.num_leaves {
            return None;
        }
        let mut siblings = Vec::new();
        let mut idx = index;
        for level in &self.levels[..self.levels.len() - 1] {
            let size = level.len();
            if idx % 2 == 0 {
                if idx + 1 < size {
                    siblings.push(level[idx + 1]); // sibling on the right
                }
                // else: promoted, no sibling at this level
            } else {
                siblings.push(level[idx - 1]); // sibling on the left
            }
            idx /= 2;
        }
        Some(Proof {
            index,
            num_leaves: self.num_leaves,
            siblings,
        })
    }

    /// Verify that `leaf_hash` at the proof's index reproduces `root`.
    pub fn verify(leaf_hash: u64, proof: &Proof, root: u64) -> bool {
        if proof.index >= proof.num_leaves {
            return false;
        }
        let mut h = leaf_hash;
        let mut idx = proof.index;
        let mut size = proof.num_leaves;
        let mut sib = proof.siblings.iter();
        while size > 1 {
            if idx % 2 == 0 {
                if idx + 1 < size {
                    match sib.next() {
                        Some(&s) => h = hash_internal(h, s),
                        None => return false,
                    }
                }
                // else promoted: h carries up unchanged
            } else {
                match sib.next() {
                    Some(&s) => h = hash_internal(s, h),
                    None => return false,
                }
            }
            idx /= 2;
            size = size.div_ceil(2);
        }
        // all siblings must have been consumed.
        sib.next().is_none() && h == root
    }

    /// The indices of leaves that differ from `other` (both trees must have the
    /// same leaf count; otherwise `None`). Descends only where subtree hashes
    /// disagree, so the cost scales with the number of differences.
    pub fn diff(&self, other: &MerkleTree) -> Option<Vec<usize>> {
        if self.num_leaves != other.num_leaves {
            return None;
        }
        let mut out = Vec::new();
        if self.num_leaves == 0 {
            return Some(out);
        }
        let top = self.levels.len() - 1;
        self.descend(other, top, 0, &mut out);
        Some(out)
    }

    /// Recursive subtree comparison: at `level`/`idx`, if the two hashes match,
    /// the whole subtree is identical and is skipped; otherwise recurse to the
    /// children, collecting differing leaf indices.
    fn descend(&self, other: &MerkleTree, level: usize, idx: usize, out: &mut Vec<usize>) {
        let a = self.levels[level].get(idx);
        let b = other.levels[level].get(idx);
        if a == b {
            return; // identical subtree (or both absent)
        }
        if level == 0 {
            out.push(idx);
            return;
        }
        let child = level - 1;
        self.descend(other, child, idx * 2, out);
        if idx * 2 + 1 < self.levels[child].len() {
            self.descend(other, child, idx * 2 + 1, out);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tree(words: &[&str]) -> MerkleTree {
        MerkleTree::from_leaves(words)
    }

    #[test]
    fn empty_tree() {
        let t = MerkleTree::from_leaves::<&[u8]>(&[]);
        assert!(t.is_empty());
        assert_eq!(t.root(), EMPTY_ROOT);
        assert!(t.proof(0).is_none());
    }

    #[test]
    fn single_leaf_root_is_leaf_hash() {
        let t = tree(&["only"]);
        assert_eq!(t.len(), 1);
        assert_eq!(t.root(), hash_leaf(b"only"));
        assert_eq!(t.height(), 0);
    }

    #[test]
    fn root_is_deterministic() {
        let a = tree(&["a", "b", "c", "d"]);
        let b = tree(&["a", "b", "c", "d"]);
        assert_eq!(a.root(), b.root());
    }

    #[test]
    fn changing_a_leaf_changes_root() {
        let a = tree(&["a", "b", "c", "d"]);
        let b = tree(&["a", "X", "c", "d"]);
        assert_ne!(a.root(), b.root());
    }

    #[test]
    fn order_matters() {
        let a = tree(&["a", "b"]);
        let b = tree(&["b", "a"]);
        assert_ne!(a.root(), b.root());
    }

    #[test]
    fn proofs_verify_for_all_indices() {
        for n in 1..=17usize {
            let words: Vec<String> = (0..n).map(|i| format!("leaf{i}")).collect();
            let t = MerkleTree::from_leaves(&words);
            let root = t.root();
            for i in 0..n {
                let proof = t.proof(i).unwrap();
                let lh = hash_leaf(words[i].as_bytes());
                assert!(
                    MerkleTree::verify(lh, &proof, root),
                    "n={n} index={i} failed"
                );
            }
        }
    }

    #[test]
    fn tampered_proof_fails() {
        let words = ["a", "b", "c", "d", "e"];
        let t = MerkleTree::from_leaves(&words);
        let root = t.root();
        let mut proof = t.proof(2).unwrap();
        let lh = hash_leaf(b"c");
        assert!(MerkleTree::verify(lh, &proof, root));
        // wrong leaf
        assert!(!MerkleTree::verify(hash_leaf(b"X"), &proof, root));
        // corrupted sibling
        if let Some(s) = proof.siblings.first_mut() {
            *s ^= 1;
        }
        assert!(!MerkleTree::verify(lh, &proof, root));
    }

    #[test]
    fn odd_leaf_count() {
        let t = tree(&["a", "b", "c"]);
        let root = t.root();
        for (i, w) in ["a", "b", "c"].iter().enumerate() {
            let p = t.proof(i).unwrap();
            assert!(MerkleTree::verify(hash_leaf(w.as_bytes()), &p, root));
        }
    }

    #[test]
    fn diff_finds_changed_leaves() {
        let a = tree(&["a", "b", "c", "d", "e", "f", "g", "h"]);
        let b = tree(&["a", "B", "c", "d", "e", "F", "g", "h"]);
        let d = a.diff(&b).unwrap();
        assert_eq!(d, vec![1, 5]);
    }

    #[test]
    fn diff_empty_when_identical() {
        let a = tree(&["x", "y", "z", "w"]);
        let b = tree(&["x", "y", "z", "w"]);
        assert!(a.diff(&b).unwrap().is_empty());
    }

    #[test]
    fn diff_all_when_all_change() {
        let a = tree(&["a", "b", "c"]);
        let b = tree(&["1", "2", "3"]);
        assert_eq!(a.diff(&b).unwrap(), vec![0, 1, 2]);
    }

    #[test]
    fn diff_requires_same_length() {
        let a = tree(&["a", "b"]);
        let b = tree(&["a", "b", "c"]);
        assert!(a.diff(&b).is_none());
    }

    #[test]
    fn diff_single_change_in_large_tree() {
        let n = 1000;
        let base: Vec<String> = (0..n).map(|i| format!("v{i}")).collect();
        let a = MerkleTree::from_leaves(&base);
        let mut changed = base.clone();
        changed[742] = "CHANGED".to_string();
        let b = MerkleTree::from_leaves(&changed);
        assert_eq!(a.diff(&b).unwrap(), vec![742]);
    }

    #[test]
    fn serde_round_trip() {
        let t = tree(&["a", "b", "c", "d"]);
        let j = serde_json::to_string(&t).unwrap();
        let back: MerkleTree = serde_json::from_str(&j).unwrap();
        assert_eq!(t, back);
        assert_eq!(t.root(), back.root());
    }

    #[test]
    fn schema_version_is_set() {
        assert_eq!(SCHEMA_VERSION, "1.0.0");
    }
}
