# Knowledge index

## Product technical (docs/)
Liberty / Lifestyle / Income PDFs — primary RAG for FA figures.

## Lessons you add (`docs/learn/<topic>/`)
From **Learn & ingest** pick a shelf: product, design, psychology, craft, practice, misc.
Indexed as `learn:<topic>:<filename>` so Chat can cite them without mixing them into a benefit table.

## Practice markdown already in docs/
FAIS ROA guide, risk literacy, performance psychology, website mockup training, maximization.

## Doctrine the rooms load directly
- `craft_design_doctrine.md` — what a shop page is for (loaded by design_reason)
- `craft_html_doctrine.md` — writing the document yourself, and what the gate refuses (loaded by html_author)
- `desk_separation_doctrine.md` — Craft leads and FA clients are never one record

After adding files in the desk, they ingest immediately. Or `python ingest.py`.
