# Retention and erasure

How long client information is kept, and how it is removed when it should be.

This document describes control #6 of the compliance-hardening list. It is
written for a compliance officer, not for a developer.

## The two obligations

They pull in opposite directions, which is why this is a considered process and
not a delete button.

**POPIA s14** says personal information must not be kept for longer than is
necessary — *except* where another law requires it.

**The FAIS General Code of Conduct** requires advice records to be kept for
five years after the advice was given or after the product ends.

So the desk's position is not "delete when asked". It is: keep for the period
the law requires, know when that period expires, and be able to erase
completely when it does. The period is named with its basis in the code, not
left as a bare number somebody later tidies up.

## Nothing is erased on a timer

Retention expiry is **reported**. A person erases.

A desk that quietly destroyed records a regulator may still call for would be a
worse failure than one that keeps them slightly too long, and "the software did
it automatically" is not a defence anyone wants to offer.

```bash
python retention.py due
```

Only closed clients are listed. An active client's records are not up for
erasure however old they are, and a list mixing the two would train whoever
reads it to skim.

## The part that is easy to get wrong

A client's personal information lives in **five** places, built at different
times by different code:

1. the vault files under `clients/<id>/`
2. the client database — five tables, all keyed on the client id
3. **the page index**, as `client:<id>:<filename>` rows carrying the extracted
   text of their documents
4. **the answer log**, where an answer that quoted their file contains their
   information in its own text
5. **the document action log**, which records what was done to their documents
   and by whom

The fifth was added after this module was written, and adding it without
teaching `erase()` about it would have been precisely the failure described
here. It was surveyed and cleared in the same change, and the erasure test
would have gone red otherwise.

An erasure that removes the folder and the database rows looks complete, is
reported as complete, and leaves the desk able to quote the client's income and
ID number out of the index for as long as the index survives.

So the survey comes first, and shows all four:

```bash
python retention.py where thabo_molefe
```

```
Where thabo_molefe exists
==============================================
  vault files                1
    documents                1
    notes                    1
  database rows              3
  index pages                1   the extracted text of their documents
  answer log rows            1   redacted, not deleted
```

The number that matters is usually the one you did not expect.

## Erasing

```bash
python retention.py erase thabo_molefe --by "M. Naidoo" --reason "..."     # dry run
python retention.py erase thabo_molefe --by "M. Naidoo" --confirm          # for real
```

**A dry run is the default.** The destructive reading of a one-word command
should be the one you have to ask for. Over HTTP the same rule holds: the
`confirm` flag must be present and true, because a missing field must not mean
"destroy it".

An erasure needs a name against it, and over HTTP that name is taken from the
credential, not from the request body.

**Completeness is verified, not assumed.** After the deletions run, the client
is surveyed again, and `complete` is set only if all four places come back
empty. Reporting success because the delete statements ran without error is
exactly how an erasure comes to be certified while the index still holds the
pages.

The index's source fingerprint is cleared along with the pages. Leaving it
would let a later indexing run decide the document was "unchanged" and skip
re-reading it.

## The answer log is redacted, not deleted

Its rows are the audit trail of advice that was given. Deleting them would put
a hole in the record of what happened, which is the opposite of what a review
needs.

The personal information in a row is the question, the answer text, the client
id and the filenames of the documents cited — a client document's filename is
frequently the client's name. Those are blanked and replaced with a distinct
marker, so a reviewer can tell an erased answer from an empty one.

What stays: the time, the room, the model, how long it took, and the retrieval
snapshot. **What was said is gone; that something was said, and from which
document versions, remains provable.**

## The receipt

Every completed erasure writes a receipt: the client id, who did it, when, and
the four counts.

It holds **no personal information** — not the name, not the content, not the
filenames. A receipt that recorded what was erased would be a copy of the thing
that was erased.

```bash
python retention.py receipts
```

## When a rep leaves

Their access is revoked with `python desk_users.py disable <id>` — which does
not delete the person, because their name is attached to approvals and to
answers that happened.

Their clients' records are a separate question and follow the rules above:
records inside the FAIS period stay, whoever wrote them. Erasure is by client
and by retention date, never by adviser.

## What this does not do

- It does not erase backups. `vault_backup.py` snapshots are content-addressed
  archives; a client erased from the live vault is still in any snapshot taken
  before the erasure, and pruning those is a separate, deliberate act.
- It does not reach data that left the desk — anything emailed, exported or
  printed.
- It does not decide whether a client's retention period has actually started.
  It reads the client's status and last activity date; if those are wrong, the
  due list is wrong.
