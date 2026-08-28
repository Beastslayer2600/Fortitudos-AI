# Risk Product Technical Literacy — Adviser Quick Reference

**Use:** Orientation for interpreting Liberty-style technical guides.  
**Always verify** on the indexed PDF page before quoting to a client. Guides change by version and benefit option.

## Concepts that drive claims (and ROA risk disclosure)

### Waiting period (income / disability style)
Time the life assured must remain disabled/impaired before the claim is admitted. Income-style benefits often offer selectable periods (e.g. 1, 3, 6, 12, 24 months; sometimes 7-day backdated for certain self-employed categories). Shorter waiting period → higher premium; longer → more client liquidity risk.

### Survival period (critical illness / lifestyle style)
Period the life assured must survive after the insured event before the benefit pays. **Not universal.** Example pattern from Lifestyle Protector family technical material: some accelerated Living Lifestyle variants state **no survival period**; Living Lifestyle Protector (income-linked style) material has described a **14-day survival period**. Always check the **specific benefit name** and guide version.

### Severity / payment percentage
Critical-illness style benefits often pay a **percentage of sum assured** by severity tier (e.g. 25% / 50% / 100%) or multiples of an income sum assured (e.g. 3× vs 24× patterns on some Lifestyle structures). Tables are page-level objects — do not paraphrase percentages from memory.

### SCIDEP / ASISA definitions
Where a guide states compliance with standardised critical illness definitions (ASISA / SCIDEP), say so and still cite the guide page; standardisation does not remove product-specific options (Top-Up, Extended, Female, Child variants).

### Acceleration vs stand-alone
Accelerated benefits reduce the residual life cover; stand-alone does not. Material for replacement and estate discussions.

## Query patterns that need hybrid retrieval

| Client / adviser question type | Why lexical match matters |
|--------------------------------|---------------------------|
| “What % for hearing loss at 90 dB both ears?” | Exact clinical thresholds in tables |
| “Survival period on Living Lifestyle Protector?” | Benefit-name disambiguation |
| “Waiting period options on Income Protector?” | Enumerated options in tables |
| “Is there a retrenchment benefit?” | Product name + caps (e.g. monthly max, duration) |

Fortitudo hybrid search (BM25 + dense + RRF) is designed for these table-heavy queries.

## Adviser workflow with the index

1. `ask.py --show "…"` — confirm the right pages before generation (no model wait).
2. Full ask or Desk Ask — cited answer.
3. Open the PDF at the cited page before client meeting.
4. Evidence Pack draft — client-facing explanation of the **verified** mechanic only.

## Version discipline

Technical guides are versioned (e.g. July 2026 Lifestyle Protector guide). After dropping a new PDF in `docs/`, run `python ingest.py` (or `--rebuild` if the file replaced an existing name). Stale indexes create confident wrong citations.
