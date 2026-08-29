"""
Fortitudo AI — hybrid retrieval (dense + BM25 + Reciprocal Rank Fusion)

Research basis (2025–2026 financial RAG):
- Page-level chunks are a strong default for technical PDFs and stable citations.
- Dense alone misses rare clinical/legal tokens (otosclerosis, tympanosclerosis).
- BM25 alone misses paraphrase. Hybrid + RRF is the production default.
- RRF merges by rank (score-scale agnostic): score = sum 1/(k + rank).
"""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

import store
from llm import embed
from config import TOP_K, KEYWORD_BOOST, MAX_PAGE_CHARS

TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9\-']{1,}", re.I)

STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "else", "when",
    "at", "by", "from", "for", "with", "in", "on", "to", "of", "up", "out",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "what", "which", "who", "whom", "this", "that", "these",
    "those", "am", "how", "much", "many", "my", "your", "his", "her", "its",
    "our", "their", "can", "could", "will", "would", "should", "may", "might",
    "must", "about", "above", "after", "again", "against", "all", "any", "as",
    "because", "before", "below", "between", "both", "each", "few", "further",
    "here", "there", "into", "more", "most", "no", "nor", "not", "only", "other",
    "own", "same", "so", "some", "such", "than", "too", "very", "just", "now",
    "client", "adviser", "please", "tell", "me", "under", "does", "pay",
}

# Domain synonyms expand sparse match for SA risk-product language without an LLM call.
SYNONYMS = {
    # Risk / clinical (FA product tables)
    "hearing": ["deafness", "deaf", "audiometry", "otosclerosis", "tympanosclerosis"],
    "deafness": ["hearing", "deaf"],
    "blindness": ["vision", "sight", "ocular", "eye"],
    "cancer": ["malignant", "tumour", "tumor", "carcinoma", "neoplasm"],
    "heart": ["cardiac", "myocardial", "coronary"],
    "stroke": ["cerebrovascular", "cva"],
    "disability": ["incapacity", "occupational", "impairment"],
    "waiting": ["deferred", "deferment", "survival"],
    "survival": ["waiting", "deferment"],
    "retrenchment": ["redundancy", "retrenched"],
    "severity": ["tier", "percentage", "payout"],
    # FAIS / process
    "fica": ["identity", "kyc", "verification"],
    "fna": ["needs", "analysis"],
    "roa": ["record", "advice"],
    "replacement": ["switching", "replaced"],
    # Drama / eisteddfod (Stage 2)
    "monologue": ["solo", "speech", "character"],
    "duologue": ["dialogue", "samespraak"],
    "eisteddfod": ["allegretto", "festival", "competition"],
    "adjudication": ["adjudicator", "marking", "judging"],
    "projection": ["volume", "voice", "articulation"],
    "articulation": ["diction", "clarity", "enunciation"],
}

RRF_K = 60
CANDIDATE_POOL = 24  # retrieve more, fuse, then cut to TOP_K


def tokenize(text: str) -> List[str]:
    return [t.lower() for t in TOKEN_RE.findall(text or "") if t.lower() not in STOPWORDS]


def expand_query_tokens(tokens: List[str]) -> List[str]:
    out = list(tokens)
    seen = set(tokens)
    for t in tokens:
        for syn in SYNONYMS.get(t, []):
            if syn not in seen:
                out.append(syn)
                seen.add(syn)
    return out


class BM25Index:
    """Okapi BM25 over in-memory page texts. Rebuilt when the vector cache refreshes."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.docs: List[List[str]] = []
        self.doc_len: List[int] = []
        self.avgdl = 0.0
        self.df: Counter = Counter()
        self.N = 0
        self._built_for: Optional[int] = None

    def build(self, texts: List[str], fingerprint: int):
        if self._built_for == fingerprint and self.N == len(texts):
            return
        self.docs = [tokenize(t) for t in texts]
        self.doc_len = [len(d) or 1 for d in self.docs]
        self.N = len(self.docs)
        self.avgdl = sum(self.doc_len) / max(self.N, 1)
        self.df = Counter()
        for d in self.docs:
            for term in set(d):
                self.df[term] += 1
        self._built_for = fingerprint

    def scores(self, query_tokens: List[str]) -> np.ndarray:
        if not self.N:
            return np.zeros(0, dtype=np.float32)
        scores = np.zeros(self.N, dtype=np.float32)
        for term in query_tokens:
            df = self.df.get(term, 0)
            if df == 0:
                continue
            idf = math.log(1 + (self.N - df + 0.5) / (df + 0.5))
            for i, doc in enumerate(self.docs):
                # count occurrences
                tf = 0
                for w in doc:
                    if w == term:
                        tf += 1
                if tf == 0:
                    continue
                denom = tf + self.k1 * (1 - self.b + self.b * self.doc_len[i] / self.avgdl)
                scores[i] += idf * (tf * (self.k1 + 1)) / denom
        return scores


_BM25 = BM25Index()


def _rrf_fuse(rank_lists: List[List[int]], k: int = RRF_K) -> Dict[int, float]:
    fused: Dict[int, float] = {}
    for ranked in rank_lists:
        for rank, doc_id in enumerate(ranked):
            fused[doc_id] = fused.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
    return fused


# Written by the model, not filed by a person. Advisor answers under FAIS, so
# these stay out of its corpus; their own rooms still read them.
MACHINE_WRITTEN_SOURCES = ("learn:craft:", "learn:sight:")

# Rooms that answer as the adviser and must cite a filed page.
ADVISER_ROOMS = ("fa", "roa")


def corpus_exclusions(room: str) -> Tuple[str, ...]:
    return MACHINE_WRITTEN_SOURCES if (room or "fa").lower() in ADVISER_ROOMS else ()


def search(
    conn,
    query: str,
    top_k: int = TOP_K,
    exclude_prefixes: Tuple[str, ...] = (),
) -> List[Tuple[Any, float]]:
    """Hybrid dense + BM25 retrieval with Reciprocal Rank Fusion.

    `exclude_prefixes` drops sources by name before scoring, so a room can be
    held to the corpus it is allowed to answer from.
    """
    rows, matrix = store.load_all(conn)
    if exclude_prefixes:
        keep = [i for i, r in enumerate(rows) if not str(r[1]).startswith(exclude_prefixes)]
        if len(keep) != len(rows):
            rows = [rows[i] for i in keep]
            matrix = matrix[keep] if len(keep) else matrix[:0]
    if not rows:
        return []

    texts = [r[3] for r in rows]
    _BM25.build(texts, fingerprint=len(rows) ^ (hash(texts[0][:80]) if texts else 0))

    # Dense
    qvec = np.asarray(embed(query)[0], dtype=np.float32)
    qnorm = np.linalg.norm(qvec) or 1.0
    dense_scores = matrix @ (qvec / qnorm)

    # BM25 with light query expansion
    q_tokens = expand_query_tokens(tokenize(query))
    bm25_scores = _BM25.scores(q_tokens)

    pool = min(CANDIDATE_POOL, len(rows))
    dense_rank = list(np.argsort(-dense_scores)[:pool])
    bm25_rank = list(np.argsort(-bm25_scores)[:pool]) if bm25_scores.size else []

    fused = _rrf_fuse([dense_rank, bm25_rank])

    # Mild extra boost when query tokens appear literally (table labels, product names)
    if q_tokens:
        for i, r in enumerate(rows):
            if i not in fused:
                continue
            lowered = r[3].lower()
            hits = sum(1 for t in q_tokens if t in lowered)
            if hits:
                fused[i] += KEYWORD_BOOST * (hits / max(len(q_tokens), 1)) * 0.15

    ordered = sorted(fused.keys(), key=lambda i: fused[i], reverse=True)[:top_k]
    return [(rows[i], float(fused[i])) for i in ordered]


def build_context(results: List[Tuple[Any, float]]) -> str:
    blocks = []
    for (rid, source, page, text, _emb), score in results:
        snippet = text[:MAX_PAGE_CHARS]
        if len(text) > MAX_PAGE_CHARS:
            snippet += "\n[... page truncated ...]"
        blocks.append(f"--- SOURCE: {source} | PAGE {page} | retrieval_score={score:.4f} ---\n{snippet}")
    return "\n\n".join(blocks)
