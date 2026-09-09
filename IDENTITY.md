# The ring-fence

How this codebase stays shareable while the desk it runs still belongs to
somebody.

This is the architectural decision the two-product plan marks as urgent: a
generic core is shared, and the employer-specific part never is. Get it wrong
once and the shared code is contaminated.

## The problem

The desk used to state its own identity in about fifteen files — an FSP number
in the advice room's system prompt, an adviser's name in the Record of Advice
defaults, a studio name and phone number in the outreach copy, an insurer's
product name in a routing regex and a doctrine comment.

Each one was correct when it was written. Together they meant the core could
not be handed to anyone without handing over one person's regulatory identity —
and, more seriously, that employer material was living in a repository meant to
be provably clean of it.

## Identity is data

`backend/identity.py` and `src/lib/identity.ts` hold the desk's own facts:
adviser, FSP body and number, practice, studio, contact details, and the name
of a product the desk knows about.

**Defaults are blank or generic.** Not a plausible placeholder — a desk that
ships with `FSP 00000` will eventually put that on a document. Where a field is
unset, the code using it omits the claim rather than inventing one, which is
the rule the rest of the desk already follows about facts it does not have. So:

- an unconfigured advice room says "You are an evidence engine for a financial
  adviser" and names no licence
- an unconfigured FNA leaves the FSP field blank, where it is marked blank and
  chased, rather than filled with a number that is silently wrong on a signed
  document
- a half-configured desk states half a fact (`Some Body FSP 1234`) rather than
  a malformed whole one

**Real values live outside the repository** — `identity.json` beside the vault,
or `FORTITUDO_ID_*` in the environment, which wins. Both are in `.gitignore`,
for the same reason the client vault is: what stops employer material reaching
a public remote is that it was never in the working tree.

```bash
python backend/identity.py          # what this desk currently claims
```

The browser fetches it once from `GET /api/identity` on mount. Anything read
before that lands gets the generic defaults.

One consequence worth knowing: prompts are now **built per call**, not frozen
at import. `roleBoundary()` and `voiceSystem()` replace the constants that used
to be evaluated when the module loaded — which would have captured the
unconfigured text and used it for the rest of the session.

## The fence is a check, not a sweep

A one-time tidy-up does not deliver this. The strings come back: a name typed
into a default, a product named in a comment, an FSP number in a prompt
somebody was improving. Each arrives looking like a small convenience rather
than like the thing that contaminates the shared codebase.

```bash
python backend/fence.py             # exit 0 clean, 1 with the lines to look at
```

It reads the identity the desk is **actually configured with** and looks for
those exact values in shared source. Deliberately not a fixed blocklist of one
person's details — a blocklist protects whoever wrote it and nobody else, and
the next adviser's name would sail straight through. What is forbidden is *the
configured identity appearing in shared code*, whoever's it is.

Two things it does differently from the obvious version:

- **Shipped defaults are skipped.** Fencing `"the studio"` matches ordinary
  prose and reports the absence of identity as a breach — the one result that
  would make people stop running it.
- **An unconfigured desk is not reported as a pass.** Nothing to look for is
  not the same as nothing to find, and it says so.

Employer and product names (`Liberty Group`, `Lifestyle Protector`) are
forbidden outright, because an employer's name is not one of the desk's own
facts and cannot be read from settings.

The fence runs as a section of `eval_desk.py`, so it is checked on every
evaluation rather than when somebody remembers.

## Three kinds of file

| Kind | Rule |
|---|---|
| **shared** — `backend/`, `src/`, `scripts/` | No configured identity, no employer or product material |
| **local** — `backend/docs/learn/`, `backend/docs/clients/`, `backend/data/` | The adviser's own content. Not fenced, and not shareable either |
| **identity** — `identity.py`, `fence.py`, `model/Modelfile` | Identity is expected here |

The fence lists the local files every time it runs. That list is the answer to
"what would have to come out", which is the question it is really being asked.

## The Modelfile

A model built from a Modelfile carries its `SYSTEM` block inside the model,
wherever that model goes — so a name compiled in there travels further than a
name in a prompt.

`backend/model/Modelfile` is therefore a template with one placeholder, and
`backend/model/build.py` fills it in at build time:

```bash
python backend/model/build.py
ollama create fortitudo -f backend/model/Modelfile.built
```

`Modelfile.built` is gitignored. An unconfigured desk builds a model belonging
to "a South African financial adviser" — true, rather than belonging to
somebody who does not use it.

## What this does not do

- It does not split the repository into `core` / `liberty` / `broker` packages.
  That is the plan's post-RE5 item; this is the precondition for it, because
  the split is worthless while the identity is scattered.
- It does not fence content — `backend/docs/learn/` and the indexed corpus are
  the adviser's own and are reported, not cleaned.
- It does not check git history. Anything committed before this still sits in
  the history and needs a separate decision.
