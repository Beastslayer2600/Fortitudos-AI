# Data residency

Where this desk's information physically sits, and how that answer stays true.

This document describes control #3 of the compliance-hardening list. POPIA s72
governs sending personal information across the border, and a desk that runs
entirely on the adviser's own machine has the easiest possible answer to give.

Which is exactly why it should not be given as a sentence. *"We are fully
local"* is what every vendor says, and a residency claim decays quietly —
somebody adds a web font, a map tile, an analytics beacon — while the document
still says it is true.

So the answer is computed, not asserted:

```bash
python backend/residency.py      # exit 0 clean, 1 with the findings
```

It reports three things from the running configuration.

## Storage

Every directory and database the desk writes to, whether it holds personal
information, and whether it sits under the data root.

The data root is the thing an adviser backs up, encrypts, and can point at when
asked where the client information lives. **A store holding personal data
outside it is personal information in a place nobody is thinking about**, and
that is the only condition flagged. A directory of product PDFs living in the
repository is where it is meant to be; marking that too would teach whoever
reads the report to ignore the marks.

| Store | Personal data |
|---|---|
| Client vault, client records | yes |
| Page index | **yes** — see below |
| Answer log | yes |
| User directory | yes |
| Drop zone, review area | yes |
| Product documents, mockups, register, receipts, identity, token | no |

### The page index counts as personal data

It holds `client:<id>:<filename>` rows carrying the extracted text of client
documents — income, ID numbers, cover amounts. It is not "just the product
index", and treating it as one is how it came to live inside the repository
while the client vault was deliberately kept outside it.

**This check found that.** The index now defaults to the data root alongside
the vault. An index already sitting at the old in-repo path keeps being used,
because moving somebody's index out from under them on upgrade looks exactly
like losing it — the report names the old path and the remedy instead.

## Compute

Every job, the host its model work resolves to, and whether that host is this
machine.

All of them are local except Craft, which is the web-design room and touches no
client data or product literature. Anything carrying client data is pinned to
localhost by `compute.py` even when a remote host is configured, and a job with
no name is treated as sensitive — so a job added later is pinned by default
rather than exempt by omission.

There is no cloud fallback. If the local model is unavailable the desk fails.

## Outbound

Every external host named anywhere in the source, **found by reading the source
each time** rather than from a list somebody maintains. A maintained list is
precisely what goes stale.

An unclassified host is the finding. The report does not fail on egress
existing; it fails on egress nobody has explained.

Three kinds are distinguished, because they are three different disclosures:

| | Endpoint |
|---|---|
| **The desk calls this** | `api.qrserver.com` — QR image for a printed flyer |
| **Written into a generated page; the viewer's browser calls it** | `fonts.googleapis.com`, `fonts.gstatic.com` |
| **A link on a generated page; only a visitor who clicks it** | `maps.google.com`, `wa.me` |
| **Never fetched by anyone** | `schema.org` — a JSON-LD vocabulary identifier |

Only the first is egress by the desk. **`api.qrserver.com` receives the URL of
a generated mock page** when a flyer QR is printed, and only when a public host
has been configured — a localhost URL will not produce a QR at all, because a
QR pointing at localhost dies the moment it leaves the Wi-Fi. No client data is
involved either way: a flyer advertises a shop, not a client.

Running this check for the first time surfaced three hosts nobody had
classified. All three turned out to be benign links on generated shop pages —
which is the useful outcome, because until it ran, "benign" was an assumption.

## What this does not check

- **It does not check that the disk is encrypted.** That is the operating
  system's job — BitLocker or FileVault — and the desk cannot verify it
  honestly, so it says so rather than implying it.
- **It does not follow what a generated page loads once a browser opens it**,
  beyond naming the endpoints baked into the page. The desk does not fetch
  those; the viewer does.
- **It does not cover backups once they leave the machine.** A snapshot copied
  to a cloud drive is outside anything this can see, and is a decision the
  adviser makes.
- **It does not audit the network.** It reports where the desk is configured to
  send work, not what the machine is otherwise doing.

## The short answer, for a form

> All client information is held on the adviser's own machine, in a single data
> root, and all model inference runs locally on that machine. No client
> information is transmitted to any third party or across any border. The one
> outbound request the software makes is to a QR-code image service, and only
> when printing a marketing flyer for a small business — it carries a public
> web address and no client information.

Every clause of that is checked by `residency.py` and by the `data residency`
section of the evaluation harness, so it fails rather than drifting.
