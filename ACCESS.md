# Access control

Who may use the desk, and what each person may do.

This document describes control #1 of the compliance-hardening list. It is
written for a compliance officer, not for a developer.

## What was there before

One shared token. It answers a single question — *may this request in?* — and
for one adviser on one laptop that is the right amount of machinery.

The gap it leaves is specific, and it shows up in document approvals. The
register records *who approved this document*. If the approver's name comes
from whoever is calling, then anyone holding the shared token can record an
approval under anyone's name, and the register's most important field is the
one field nothing checks. **An audit trail that records a name supplied by the
caller records a claim, not a fact.**

## What is there now

Named people with their own credentials. Identity comes from the credential,
and the caller does not get to say who they are.

- **Approvals are attributed to whoever actually made them.** The name is read
  from the credential; a `by` field in the request body is ignored.
- **Answers record who asked**, in the same log row as what came back and which
  document version it came from.
- **Access is revocable** without deleting the person, because their name is
  attached to approvals and answers that already happened. Deleting the row
  would leave the audit trail pointing at nobody.
- **Only the hash of a token is stored.** A stolen copy of the directory is not
  a set of working credentials, and nobody — including whoever runs the desk —
  can read somebody else's token back out of it. A token is displayed once,
  when it is issued.

## Roles

| Role | May |
|---|---|
| `adviser` | ask, open client files, read the document register |
| `approver` | ask, read the register, **approve and withdraw documents** |
| `admin` | all of the above, plus manage users |

An approver is not an adviser's manager. They read product documents and sign
them off; a client's file is not theirs to open.

Routes are mapped to capabilities in one table rather than checked one by one,
and the check runs in the request guard before any route does — so a route
added later inherits a decision instead of quietly having none. A route nobody
has classified falls back to the lowest capability, not to no capability.

## Nothing changes for one adviser on one laptop

With no users registered, the desk behaves exactly as it did: loopback is
trusted, and remote requests need the shared token. Registering the first user
is what turns the roles on.

This matters more than it sounds. A control that forced a single adviser to
stand up a user directory before they could use their own laptop would simply
never be switched on.

Two things change the moment a directory exists, and both are deliberate:

- **Being at the keyboard stops being an identity.** Whoever walks up to the
  machine is no longer automatically the owner.
- **The shared token stops being an identity.** Otherwise the directory is
  decoration — the old key still opens everything, under nobody's name.

## Using it

```bash
python desk_users.py list
python desk_users.py add "M. Naidoo" --role approver
python desk_users.py disable <user-id>
```

`add` prints the token once. It is not stored and cannot be recovered; losing
it means issuing a new one. Hand it over on something private, not in email.

Over HTTP, users send their own token as `Authorization: Bearer <token>`.
`GET /api/users` lists the directory and the capability table — never tokens.

Where the desk is shared but has no directory yet, `FORTITUDO_LOCAL_ROLE`
narrows what a local request may do (default `admin`, on the reasoning that a
single adviser at their own machine already owns the vault).

## What this is not

**This is not SSO.** A firm running this properly should authenticate against
its own directory, and the place that would plug in is `desk_users.identify()`
— everything downstream asks for a user and a capability, not for a token.
What is here is the honest step before that: names, roles, revocation, and an
approval attributed to whoever actually made it.

It also does not do password rotation, session expiry, rate limiting, or
lockout after repeated failures. A token is valid until it is disabled.
