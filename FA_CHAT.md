# FA tool — documents into better chat

The adviser desk is only useful if the model stays on **filed pages** and **client files**, not general knowledge.

## What the chat now does

1. You ask a product question.
2. Retrieval searches the page index.
3. Follow-up turns rewrite the query with the last messages so “that waiting period” still hits the same guide.
4. If a client is selected, filed PDFs/TXT/MD are labelled as client-file extracts, separate from product guides.
5. Pinned notes / last citations stay in the prompt.
6. The model must cite SOURCE + PAGE. If it is not on a page, it must say so.

## How you run it

1. Drop product PDFs into `backend/docs/`
2. `python ingest.py`
3. File client documents on that client
4. Open Advisor, select the client, ask against the page
5. Follow-ups stay on those pages

## What it will never do

Advisor does not teach itself. Self-learning is off, and `/api/learn/teach`
files your words verbatim — it will not research a topic and file the result.

Nothing the model wrote can come back as Advisor evidence:

| Written by the model | Where it goes | Advisor sees it |
|---|---|---|
| Craft design lessons | `learn:craft:` | No |
| Sight's reading of a photo | `learn:sight:` | No |
| RoA / advice-summary drafts | the client's `99_AI_Drafts/` | No — not indexed |

Craft and Studio still read their own shelves. The rule is only that an answer
you rely on under FAIS cites a filed page, never the desk's own earlier output.

FAIS: you remain the adviser. Craft never carries FSP branding.
