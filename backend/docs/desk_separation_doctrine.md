# Two businesses, one desk

Fortitudo runs an advisory practice and a web studio from the same desk. They
share a screen. They must never share a record.

## Who is who

**FA clients** are advice clients. They exist under FAIS. They have a file: a
needs analysis, a risk profile, quotes, a record of advice. What is written on
that file is evidence, and a regulator may one day read it.

**Craft leads** are shop owners the studio sells a page to. A plumber, a salon,
a bakery. They live in the Craft ledger. They are a sales pipeline, not a
client file, and nothing about them is regulated advice.

A plumber who buys a website is a Craft lead. If that same plumber later takes
financial advice, he is *also* an FA client — as two records, never one.

## What this forbids

- A shop page built from a client's file. An FNA is not page copy. Even if the
  page would look fine, the file was gathered for advice, and using it for
  marketing is not what it was given for.
- A Craft lead filed in the client vault. Filing a shop in the vault to reach a
  feature is how the two ledgers merge, and they do not un-merge.
- A lead brief that reads like a client file — policy numbers, ID numbers,
  "record of advice", "the client file says". If a brief contains that
  language, refuse it and ask for a brief about the shop.
- Anything the model wrote entering a client file as evidence. Model output is
  a draft. It sits in the AI-drafts folder, typed as a draft, and it never
  becomes a citable source for a later answer.

## What this permits

The two may share a *view*. One list of what needs attention today can hold a
lead to follow up and a client whose FNA is due, because that is a surface, not
a record. What it must never hold is one item that is both.

Craft may also build the practice's own storefront — Fortitudo Wealth marketing
a financial planning service is Craft work about the practice, not about a
client.

## Why it is written this way

The separation is enforced in code: the router refuses a trade page from a
client record and a client-file brief from a lead. Doctrine exists so the
reasoning matches the rails rather than fighting them — so that when the code
refuses, the refusal is understood rather than worked around.
