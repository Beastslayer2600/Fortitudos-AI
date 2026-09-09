# Document governance

Who decides what the desk is allowed to answer from, and how that decision is
evidenced afterwards.

This document describes control #4 of the compliance-hardening list: document
ingestion governance. It is written for a compliance officer, not for a
developer.

## The problem it solves

Without a register, the adviser decides what the tool learns: drop a PDF into
`backend/docs/`, run the indexer, and the desk will quote it in an answer with
a citation on it. A citation looks like authority whether or not anybody
checked the document behind it.

"The adviser decided what the tool learned" is not a control. It is the absence
of one.

## What the register records

Every document the index holds has a row in `documents.db`:

| Field | Meaning |
|---|---|
| `source` | The document, as the index names it |
| `sha256` | Fingerprint of the bytes **actually indexed** |
| `pages` | How many pages of it the index holds |
| `origin` | Where it came from, in the firm's own terms |
| `status` | `unapproved`, `approved` or `withdrawn` |
| `approved_by` / `approved_at` | Who approved it, and when |
| `approved_sha` | The fingerprint they approved |
| `first_seen` / `last_seen` | When the desk first and last read it |

Alongside it, an append-only event log: every ingest, approval, supersession
and withdrawal, with the fingerprint and the person's name against it.

## The one property that matters

**Approval is of a document, not of a filename.**

A document counts as approved only when the fingerprint someone approved is
still the fingerprint the index holds. When the file changes, the two stop
matching and the approval stops applying — immediately, with nothing to
update and nobody to notify.

This is deliberately a *comparison*, not a stored flag. A flag has to be
cleared by whatever code notices the change; if any code path forgets, the
register goes on certifying a document nobody read. A comparison cannot be
forgotten because nothing has to remember it.

The register distinguishes two states that look the same from outside:

- **Unapproved** — nobody has ever signed this off.
- **Lapsed** — somebody signed it off, and then the file changed underneath
  them. This is the one that means a person should be told.

Nothing is deleted. Withdrawing a document does not erase who approved it, and
superseding an approval records the supersession rather than overwriting the
approval. The register can therefore answer *"was this approved on the day
that advice was given"* — the question actually asked at a review — and not
only *"is it approved now"*.

## The two modes

Set with `FORTITUDO_INGEST_MODE`.

### `open` (default)

Everything indexes. Documents without a current approval are recorded, and any
answer that cites one carries a line saying so:

```
[UNAPPROVED] This answer cites documents with no current approval in the
register: lifestyle_guide.pdf. They may be superseded or may never have been
checked. Confirm the version before you rely on a figure from them.
```

This is the mode a single adviser runs. Their own guides are useful before
anyone signs them off; what is not acceptable is quoting them as though
somebody had. Day-to-day use builds the register with nobody maintaining it.

### `controlled`

A product document with no current approval is not indexed at all. The refusal
happens before any extraction or embedding work, so it cannot be worked around
by re-running the indexer, and it costs nothing when it fires.

```
REFUSE lifestyle_guide.pdf  (approved fingerprint does not match this file —
                             the document changed since it was approved)
```

This is the mode a firm runs. Product documents arrive from a controlled source
with an approval on them, or they do not arrive.

**Switching between the modes is a setting, not a re-ingest**, because the
register is kept identically in both. A desk that had to be rebuilt in order to
become governable would never be made governable.

## What is governed, and what is not

Only product documents. A client's own filed FNA is evidence about that client,
not product literature somebody has to sign off, and the adviser's own filed
lessons are their notes. Both are registered under their own kind and neither
is subject to product approval — in `controlled` mode they still index
normally.

## Using it

```bash
python doc_register.py list
python doc_register.py approve "lifestyle_guide.pdf" \
    --by "M. Naidoo" --origin "product library" --note "v3, checked p1-40"
python doc_register.py withdraw "old_guide.pdf" --by "M. Naidoo" \
    --reason "recalled by the insurer"
python doc_register.py history "lifestyle_guide.pdf"
```

Over HTTP: `GET /api/documents`, `POST /api/documents/approve`,
`POST /api/documents/withdraw`. An approval with no name against it is refused
in both places — an approval nobody signed is a checkbox, and it will be read
as one.

## How it reaches the audit trail

Each answer is written to the answer log with the pages it was built from, the
snapshot fingerprint of that retrieval, and a countable `unapproved` flag set
when the answer leaned on a document with no current approval. So the question
"how often did this desk answer from something nobody had checked" has a number
against it rather than an impression.

## What this does not do

- It does not verify that the document is *correct*, only that a named person
  said they had read it.
- It does not fetch documents from a firm's library. Something still has to put
  the file where the indexer reads it; the register governs what happens next.
- It does not authenticate the approver. In `controlled` mode with multiple
  users, approvals should be made through an authenticated endpoint — see the
  access-control control, which is a separate piece of work.
