# Expert stack notes (research-backed, Aug 2026)

## Retrieval
- **Page-level indexing** retained: best average accuracy + stable citations on financial PDFs (NVIDIA 2025; multiple 2026 RAG papers).
- **Hybrid dense + BM25 + RRF** replaces naive keyword boost. RRF is score-scale agnostic; hybrid typically +10–20% recall vs dense-only on technical corpora.
- **Domain synonym expansion** (hearing↔deafness, survival↔waiting, etc.) without an LLM round-trip.
- **Document context in embeddings**: `Document: {source}\nPage: {n}\n\n{text}` at ingest time (global context > chunk-only context in finance RAG studies). Stored page text stays clean for display.

## Generation (CPU laptop)
- Default chat model: `llama3.2:3b` (RAM-bound machine).
- `num_ctx` default 3072, `num_predict` 400, `think: false`, `keep_alive: 30m`.
- `/no_think` user prefix + response strip for leaked reasoning blocks.
- System prompt states FAIS role boundary: evidence engine, not the FSP.

## Drafts
- ROA structure maps to FAIS record-of-advice expectations: info summary, products considered, recommendation+rationale, risks, fees, replacement, outstanding FICA, adviser checklist.
- Website mockups: research-backed one-pager shell + JSON copy only.

## Operational
- Re-ingest after this upgrade to refresh embeddings with document context: `python ingest.py --rebuild`
- Golden self-check: `python ask.py --show "what percentage is paid for hearing loss in both ears of 90 decibels or more"`
