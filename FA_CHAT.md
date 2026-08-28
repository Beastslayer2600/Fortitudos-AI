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

FAIS: you remain the adviser. Craft never carries FSP branding.
