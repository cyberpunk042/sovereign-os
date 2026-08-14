//! Dense (neural) retrieval over the RAG corpus, backed by the Router tier.
//!
//! # Why
//! The hybrid retriever fuses BM25 with char-n-gram embeddings. Both are lexical:
//! they match characters, not meaning. Measured against the real 3500-passage
//! corpus with a query set whose correct sources are known:
//!
//! ```text
//! literal     hit@5  6/8    MRR 0.688
//! paraphrase  hit@5  0/6    MRR 0.000
//! ```
//!
//! Six paraphrase queries, six complete misses. "which filesystem holds the
//! operating system datasets" never reaches the ZFS root-layout document;
//! "locking down the daemons that serve predictions" never reaches the inference
//! hardening doctrine. Those documents answer those questions — in different
//! words, which is precisely the thing a char-n-gram cannot see.
//!
//! This module adds a third ranking from a real embedding model (BAAI/bge-m3 on
//! the eGPU, via `/v1/embeddings`) and fuses it with the existing hybrid order.
//!
//! # Why it degrades instead of failing
//! Retrieval must keep working when the embedder does not. Every failure path —
//! tier down, timeout, malformed reply, index still building — falls back to the
//! hybrid ranking that exists today. Grounding a prompt is not worth failing a
//! request over, and a gateway that stops answering because a helper GPU is busy
//! would be a worse system than the one this improves.
//!
//! # Why the index builds in the background
//! Embedding 3500 passages takes tens of seconds. gatewayd currently starts in
//! about three, and module 84's routing waits on it — so blocking startup on the
//! embedder would slow every restart and couple the gateway's availability to a
//! model server it does not need in order to serve. The index is built on a
//! worker thread; until it is ready, retrieval is exactly what it is today.

use std::sync::Arc;

/// How many passages go in one `/v1/embeddings` call. Large enough that 3500
/// passages are ~35 requests rather than 3500, small enough that one failure
/// costs little and the request body stays well inside any proxy limit.
const EMBED_BATCH: usize = 100;

/// A dense vector per corpus passage, ordered arbitrarily.
///
/// Brute-force cosine, deliberately: 3500 × 1024 floats is a few million
/// multiply-adds, microseconds of work. An ANN index (`sovereign-ivf`,
/// `sovereign-vptree`) would add approximation error and a build step to save
/// time that is not being spent.
pub struct NeuralIndex {
    vectors: Vec<(String, Vec<f32>)>,
}

impl NeuralIndex {
    /// Number of indexed passages.
    pub fn len(&self) -> usize {
        self.vectors.len()
    }

    /// Whether the index holds nothing.
    pub fn is_empty(&self) -> bool {
        self.vectors.is_empty()
    }

    /// Build by embedding every `(id, text)` through the configured embedder.
    ///
    /// Returns `None` when embeddings are not configured or the tier cannot be
    /// reached — the caller then keeps serving the hybrid ranking.
    pub fn build(passages: &[(String, String)]) -> Option<Self> {
        if passages.is_empty() {
            return None;
        }
        let (endpoint, model) = embed_config()?;
        let mut vectors = Vec::with_capacity(passages.len());
        for batch in passages.chunks(EMBED_BATCH) {
            let texts: Vec<&str> = batch.iter().map(|(_, t)| t.as_str()).collect();
            let embedded = match embed(&endpoint, &model, &texts) {
                Ok(v) if v.len() == texts.len() => v,
                Ok(v) => {
                    // A partial batch would silently misalign ids and vectors —
                    // every later passage attributed to the wrong document. Refuse
                    // the whole index rather than build a subtly wrong one.
                    eprintln!(
                        "sovereign-gatewayd: neural index aborted — embedder returned {} vectors \
                         for {} passages",
                        v.len(),
                        texts.len()
                    );
                    return None;
                }
                Err(e) => {
                    eprintln!("sovereign-gatewayd: neural index aborted — {e}");
                    return None;
                }
            };
            for ((id, _), vec) in batch.iter().zip(embedded) {
                vectors.push((id.clone(), normalize(vec)));
            }
        }
        eprintln!(
            "sovereign-gatewayd: neural RAG index ready — {} passage(s) embedded via {endpoint}",
            vectors.len()
        );
        Some(Self { vectors })
    }

    /// Ids of the `k` nearest passages to `query`, best-first. Empty when the
    /// query cannot be embedded — the caller falls back to the hybrid order.
    pub fn rank(&self, query: &str, k: usize) -> Vec<String> {
        if self.vectors.is_empty() || k == 0 {
            return Vec::new();
        }
        let Some((endpoint, model)) = embed_config() else {
            return Vec::new();
        };
        let q = match embed(&endpoint, &model, &[query]) {
            Ok(mut v) if !v.is_empty() => normalize(v.remove(0)),
            _ => return Vec::new(),
        };
        let mut scored: Vec<(f32, &String)> = self
            .vectors
            .iter()
            .filter(|(_, v)| v.len() == q.len())
            .map(|(id, v)| (dot(&q, v), id))
            .collect();
        // Descending score; ties broken by id so the order is deterministic and
        // two runs of the benchmark cannot disagree by luck.
        scored.sort_by(|a, b| {
            b.0.partial_cmp(&a.0)
                .unwrap_or(std::cmp::Ordering::Equal)
                .then_with(|| a.1.cmp(b.1))
        });
        scored.into_iter().take(k).map(|(_, id)| id.clone()).collect()
    }
}

/// `(endpoint, model)` for the embeddings backend, or `None` when unset — the
/// same pair `/v1/embeddings` relays to, so retrieval and the public route can
/// never disagree about which model is in use.
fn embed_config() -> Option<(String, String)> {
    let endpoint = std::env::var("SOVEREIGN_GATEWAY_EMBED_ENDPOINT").ok()?;
    let endpoint = endpoint.trim().to_string();
    if endpoint.is_empty() {
        return None;
    }
    let model = std::env::var("SOVEREIGN_GATEWAY_EMBED_MODEL")
        .unwrap_or_default()
        .trim()
        .to_string();
    Some((endpoint, model))
}

/// POST one batch to the embedder and return its vectors in request order.
fn embed(endpoint: &str, model: &str, texts: &[&str]) -> Result<Vec<Vec<f32>>, String> {
    let mut body = serde_json::json!({ "input": texts });
    if !model.is_empty() {
        body["model"] = serde_json::Value::String(model.to_string());
    }
    let (status, resp) = crate::http::proxy_forward(endpoint, "/v1/embeddings", &body.to_string())?;
    if status != 200 {
        return Err(format!("embedder {endpoint} returned {status}: {}", resp.trim()));
    }
    let doc: serde_json::Value =
        serde_json::from_str(&resp).map_err(|e| format!("embedder reply is not JSON: {e}"))?;
    let data = doc
        .get("data")
        .and_then(serde_json::Value::as_array)
        .ok_or_else(|| "embedder reply has no `data` array".to_string())?;
    // Order by the reply's own `index` rather than trusting arrival order: the
    // OpenAI shape carries it precisely because the server may reorder.
    let mut out: Vec<(u64, Vec<f32>)> = Vec::with_capacity(data.len());
    for (i, item) in data.iter().enumerate() {
        let idx = item
            .get("index")
            .and_then(serde_json::Value::as_u64)
            .unwrap_or(i as u64);
        let v: Vec<f32> = item
            .get("embedding")
            .and_then(serde_json::Value::as_array)
            .ok_or_else(|| "an embedding entry has no `embedding` array".to_string())?
            .iter()
            .filter_map(serde_json::Value::as_f64)
            .map(|f| f as f32)
            .collect();
        out.push((idx, v));
    }
    out.sort_by_key(|(i, _)| *i);
    Ok(out.into_iter().map(|(_, v)| v).collect())
}

/// L2-normalize so a dot product IS cosine similarity — done once per vector at
/// index time instead of once per comparison at query time.
fn normalize(mut v: Vec<f32>) -> Vec<f32> {
    let norm = v.iter().map(|x| x * x).sum::<f32>().sqrt();
    if norm > 0.0 {
        for x in &mut v {
            *x /= norm;
        }
    }
    v
}

fn dot(a: &[f32], b: &[f32]) -> f32 {
    a.iter().zip(b).map(|(x, y)| x * y).sum()
}

/// Build a [`NeuralIndex`] for `store` on a worker thread and hand it to `install`.
///
/// Startup must not wait on a GPU: gatewayd comes up in about three seconds and
/// module 84's routing blocks on it, so embedding 3500 passages inline would make
/// every restart tens of seconds slower and tie the gateway's availability to a
/// model server it does not need in order to serve.
pub fn build_in_background<F>(store: Arc<sovereign_retrieval::HybridStore>, install: F)
where
    F: FnOnce(Arc<NeuralIndex>) + Send + 'static,
{
    if embed_config().is_none() {
        return; // embeddings not configured — hybrid-only, silently and correctly
    }
    std::thread::spawn(move || {
        let passages = store.entries();
        if let Some(idx) = NeuralIndex::build(&passages) {
            install(Arc::new(idx));
        }
    });
}
