# Knowledge index — what to ingest and how to use it

## Product technical (already in docs/)
Liberty / Lifestyle / Income / ADDLIB / retrenchment PDFs — primary RAG corpus for FA questions.

## Practice knowledge (markdown — ingest with the PDFs)

| File | Use when |
|------|----------|
| `fais_roa_expert_guide.md` | ROA drafts, compliance posture, Ombud readiness |
| `risk_product_literacy.md` | Waiting/survival/severity literacy; query design |
| `drama_adjudication_knowledge.md` | Stage-2 drama coaching & adjudication |
| `coding_architecture.md` | Maintaining and extending the codebase |
| `expert_stack_notes.md` | Retrieval/LLM design rationale |
| `website_mockup_training.md` | Client/practice website mockups |
| `website_copy_draft.md` | Fortitudo Wealth copy bank |
| `maximization_guide.md` | Practice workflow maximization |
| `performance_psychology_2026.md` | Music/dance/drama performance psychology |

After adding or editing any of these:

```bat
python ingest.py
```

Markdown is split on blank lines into page-like sections for citation.

## Recommended ask habits

- Product figure → technical PDF via hybrid retrieval.
- “How should this ROA be structured?” → FAIS guide.
- “What is a survival period?” → literacy doc + confirm on product PDF.
