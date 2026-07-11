//! Ad-hoc probe: `cargo run --example probe -- <tokenizer.json> "text" ...`
//! Prints encode/decode for each argument against a real tokenizer.json.
use sovereign_hf_tokenizer::HfBpeTokenizer;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let bytes = std::fs::read(&args[1]).expect("read tokenizer.json");
    let tok = HfBpeTokenizer::from_tokenizer_json(&bytes).expect("load");
    println!("vocab_size={} bos={:?}", tok.vocab_size(), tok.bos_id());
    for s in &args[2..] {
        let ids = tok.encode(s);
        println!("encode({s:?}) = {ids:?}  ->decode {:?}", tok.decode(&ids));
    }
}
