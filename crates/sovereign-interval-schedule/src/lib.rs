//! `sovereign-interval-schedule` — admit the best set of non-conflicting jobs.
//!
//! One exclusive resource — a GPU timeline, a reservation calendar, a lock window —
//! and a pile of jobs, each wanting a half-open interval `[start, end)`. They cannot
//! overlap, so some must be dropped. Which set do you keep? Two classic answers,
//! both here.
//!
//! For the **most valuable** set, each job carries a weight and you want the
//! maximum total weight: that is weighted interval scheduling, solved exactly by a
//! dynamic program over jobs sorted by finish time. For each job, binary-search the
//! latest earlier job that does not overlap it, then choose the better of "skip this
//! job" and "take it, plus the best schedule that ends before it starts."
//! [`max_weight`] returns the chosen jobs and their total weight.
//!
//! For the **most jobs** regardless of value, the earliest-finish greedy is optimal:
//! repeatedly take the compatible job that frees the resource soonest. [`max_count`]
//! returns that set. Both report the original indices of the chosen jobs, in start
//! order, so the result maps straight back to the input.
//!
//! Intervals are half-open, so a job ending exactly when the next begins does *not*
//! conflict. An empty input yields an empty schedule.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the interval-schedule surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// The chosen schedule: original job indices and the total weight selected.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Schedule {
    /// Indices of the selected jobs (into the input), in start order.
    pub selected: Vec<usize>,
    /// Total weight of the selected jobs (job count for [`max_count`]).
    pub total_weight: f64,
}

/// The maximum-weight set of non-overlapping intervals (weighted interval
/// scheduling). Each input is `(start, end, weight)`; `start >= end` or a
/// non-positive weight job is ignored.
pub fn max_weight(intervals: &[(i64, i64, f64)]) -> Schedule {
    // keep only valid jobs, remembering their original indices.
    let mut jobs: Vec<(i64, i64, f64, usize)> = intervals
        .iter()
        .enumerate()
        .filter(|&(_, &(s, e, w))| s < e && w.is_finite() && w > 0.0)
        .map(|(i, &(s, e, w))| (s, e, w, i))
        .collect();
    if jobs.is_empty() {
        return Schedule {
            selected: Vec::new(),
            total_weight: 0.0,
        };
    }
    // sort by finish time.
    jobs.sort_by(|a, b| a.1.cmp(&b.1).then(a.0.cmp(&b.0)));
    let n = jobs.len();
    let finish: Vec<i64> = jobs.iter().map(|j| j.1).collect();

    // p[i] = index (1-based count) of the last job whose end <= jobs[i].start.
    let p: Vec<usize> = (0..n)
        .map(|i| {
            // binary search the rightmost j with finish[j] <= start_i.
            let start_i = jobs[i].0;
            let mut lo = 0usize;
            let mut hi = i; // search in [0, i)
            while lo < hi {
                let mid = (lo + hi) / 2;
                if finish[mid] <= start_i {
                    lo = mid + 1;
                } else {
                    hi = mid;
                }
            }
            lo // number of compatible jobs before i (1-based dp index)
        })
        .collect();

    // dp[i] = best total weight using jobs[0..i]; 1-indexed for convenience.
    let mut dp = vec![0.0f64; n + 1];
    for i in 1..=n {
        let w = jobs[i - 1].2;
        let take = w + dp[p[i - 1]];
        let skip = dp[i - 1];
        dp[i] = take.max(skip);
    }

    // reconstruct.
    let mut selected_sorted: Vec<usize> = Vec::new();
    let mut i = n;
    while i > 0 {
        let w = jobs[i - 1].2;
        let take = w + dp[p[i - 1]];
        if take >= dp[i - 1] && take == dp[i] {
            selected_sorted.push(jobs[i - 1].3); // original index
            i = p[i - 1];
        } else {
            i -= 1;
        }
    }
    selected_sorted.reverse();
    // order by start for a stable, readable result.
    selected_sorted.sort_by_key(|&idx| intervals[idx].0);

    Schedule {
        total_weight: dp[n],
        selected: selected_sorted,
    }
}

/// The maximum-*count* set of non-overlapping intervals, by the earliest-finish
/// greedy (optimal for unweighted scheduling). Each input is `(start, end)`.
pub fn max_count(intervals: &[(i64, i64)]) -> Schedule {
    let mut jobs: Vec<(i64, i64, usize)> = intervals
        .iter()
        .enumerate()
        .filter(|&(_, &(s, e))| s < e)
        .map(|(i, &(s, e))| (s, e, i))
        .collect();
    jobs.sort_by(|a, b| a.1.cmp(&b.1).then(a.0.cmp(&b.0)));

    let mut selected = Vec::new();
    let mut last_end = i64::MIN;
    for (s, e, idx) in jobs {
        if s >= last_end {
            selected.push((s, idx));
            last_end = e;
        }
    }
    selected.sort_by_key(|&(s, _)| s);
    let count = selected.len();
    Schedule {
        selected: selected.into_iter().map(|(_, i)| i).collect(),
        total_weight: count as f64,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Brute-force max-weight by enumerating all subsets (small n only).
    fn brute_max_weight(intervals: &[(i64, i64, f64)]) -> f64 {
        let n = intervals.len();
        let mut best = 0.0f64;
        for mask in 0u32..(1 << n) {
            let mut ok = true;
            let mut chosen: Vec<(i64, i64)> = Vec::new();
            let mut w = 0.0;
            for i in 0..n {
                if mask & (1 << i) != 0 {
                    let (s, e, wt) = intervals[i];
                    if s < e && wt > 0.0 {
                        chosen.push((s, e));
                        w += wt;
                    }
                }
            }
            chosen.sort();
            for win in chosen.windows(2) {
                if win[0].1 > win[1].0 {
                    ok = false;
                    break;
                }
            }
            if ok {
                best = best.max(w);
            }
        }
        best
    }

    fn non_overlapping(intervals: &[(i64, i64)], sel: &[usize]) -> bool {
        let mut spans: Vec<(i64, i64)> = sel.iter().map(|&i| intervals[i]).collect();
        spans.sort();
        spans.windows(2).all(|w| w[0].1 <= w[1].0)
    }

    #[test]
    fn empty_input() {
        assert_eq!(max_weight(&[]).total_weight, 0.0);
        assert!(max_weight(&[]).selected.is_empty());
        assert_eq!(max_count(&[]).selected.len(), 0);
    }

    #[test]
    fn single_job() {
        let s = max_weight(&[(0, 5, 3.0)]);
        assert_eq!(s.selected, vec![0]);
        assert_eq!(s.total_weight, 3.0);
    }

    #[test]
    fn picks_higher_weight_over_more_jobs() {
        // one fat job [0,10] weight 100 vs two thin jobs [0,4],[5,9] weight 1 each.
        let jobs = [(0i64, 10i64, 100.0), (0, 4, 1.0), (5, 9, 1.0)];
        let s = max_weight(&jobs);
        assert_eq!(s.total_weight, 100.0);
        assert_eq!(s.selected, vec![0]);
    }

    #[test]
    fn combines_compatible_jobs() {
        // [0,3]w5, [3,6]w5, [0,6]w8 → take the two threes (10) over the one (8).
        let jobs = [(0i64, 3i64, 5.0), (3, 6, 5.0), (0, 6, 8.0)];
        let s = max_weight(&jobs);
        assert_eq!(s.total_weight, 10.0);
        assert_eq!(s.selected, vec![0, 1]);
    }

    #[test]
    fn half_open_touching_is_compatible() {
        // [0,5) and [5,10) do not conflict.
        let jobs = [(0i64, 5i64, 1.0), (5, 10, 1.0)];
        let s = max_weight(&jobs);
        assert_eq!(s.selected.len(), 2);
    }

    #[test]
    fn max_count_greedy_optimal() {
        // classic activity selection.
        let jobs = [
            (1i64, 4i64),
            (3, 5),
            (0, 6),
            (5, 7),
            (3, 9),
            (5, 9),
            (6, 10),
            (8, 11),
            (8, 12),
            (2, 14),
            (12, 16),
        ];
        let s = max_count(&jobs);
        // the optimal is 4 activities.
        assert_eq!(s.selected.len(), 4);
        assert!(non_overlapping(&jobs, &s.selected));
    }

    #[test]
    fn all_overlapping_picks_one() {
        let jobs = [(0i64, 10i64), (1, 9), (2, 8)];
        assert_eq!(max_count(&jobs).selected.len(), 1);
        let w = max_weight(&[(0, 10, 1.0), (1, 9, 5.0), (2, 8, 2.0)]);
        assert_eq!(w.total_weight, 5.0); // the heaviest
    }

    #[test]
    fn invalid_jobs_ignored() {
        // zero-length and negative-weight jobs are dropped.
        let jobs = [(5i64, 5i64, 10.0), (0, 4, -3.0), (0, 4, 2.0)];
        let s = max_weight(&jobs);
        assert_eq!(s.total_weight, 2.0);
        assert_eq!(s.selected, vec![2]);
    }

    #[test]
    fn matches_brute_force_random() {
        let mut st = 0xABCDEF12u64;
        let mut rng = || {
            st ^= st << 13;
            st ^= st >> 7;
            st ^= st << 17;
            st
        };
        for _ in 0..200 {
            let n = 1 + (rng() % 10) as usize;
            let jobs: Vec<(i64, i64, f64)> = (0..n)
                .map(|_| {
                    let s = (rng() % 20) as i64;
                    let e = s + 1 + (rng() % 10) as i64;
                    let w = 1.0 + (rng() % 20) as f64;
                    (s, e, w)
                })
                .collect();
            let got = max_weight(&jobs).total_weight;
            let want = brute_max_weight(&jobs);
            assert!(
                (got - want).abs() < 1e-9,
                "got {got} want {want} jobs {jobs:?}"
            );
        }
    }

    #[test]
    fn selection_is_non_overlapping() {
        let jobs = [
            (0i64, 6i64, 3.0),
            (1, 4, 2.0),
            (3, 8, 4.0),
            (5, 7, 2.0),
            (8, 12, 5.0),
        ];
        let s = max_weight(&jobs);
        let spans: Vec<(i64, i64)> = jobs.iter().map(|&(a, b, _)| (a, b)).collect();
        assert!(non_overlapping(&spans, &s.selected));
        // the dp weight equals the sum of selected weights.
        let sum: f64 = s.selected.iter().map(|&i| jobs[i].2).sum();
        assert!((sum - s.total_weight).abs() < 1e-9);
    }

    #[test]
    fn serde_round_trip() {
        let s = max_weight(&[(0, 3, 5.0), (3, 6, 5.0)]);
        let j = serde_json::to_string(&s).unwrap();
        let back: Schedule = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }

    #[test]
    fn schema_version_is_set() {
        assert_eq!(SCHEMA_VERSION, "1.0.0");
    }
}
