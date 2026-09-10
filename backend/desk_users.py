"""Named people, not one shared secret.

One token for the whole desk answers "may this request in?" and nothing else.
For one adviser on one laptop that is the right amount of machinery. For a
firm it is not, and the gap shows up in a specific place: document approvals.

`approve(source, by="M. Naidoo")` takes the approver's name from whoever is
calling. A shared token means anyone holding it can record an approval under
anyone's name, so the register's most important field — who read this document
— is the one field nothing checks. An audit trail that records a name supplied
by the caller records a claim, not a fact.

So identity comes from the credential, and the caller does not get to say who
they are.

**Nothing changes for one person on one laptop.** With no users registered the
desk behaves exactly as it did: loopback is trusted, and remote requests need
the shared token. Registering the first user is what turns the roles on. A
control that forces a single adviser to run a user directory before they can
use their own laptop would simply not be turned on.

This is not SSO. A firm running this properly should authenticate against its
own directory, and the point where that would plug in is `identify()`. What is
here is the honest step before that: names, roles, revocation, and an approval
that is attributed to whoever actually made it.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from config import DATA_ROOT

USERS_DB = Path(os.environ.get("FORTITUDO_USERS_DB") or (DATA_ROOT / "users.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    role        TEXT NOT NULL DEFAULT 'adviser',
    -- Only the hash. A stolen copy of this file must not be a set of working
    -- credentials, and nobody — including whoever runs the desk — needs to be
    -- able to read somebody else's token back out of it.
    token_sha   TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT '',
    disabled_at TEXT DEFAULT '',
    note        TEXT DEFAULT ''
);
"""

ADVISER = "adviser"
APPROVER = "approver"
ADMIN = "admin"
ROLES = (ADVISER, APPROVER, ADMIN)

# What each role may do. Deliberately a small, closed list: a capability nobody
# can name is a capability nobody reviews.
CAPABILITIES = {
    ADVISER: frozenset({"ask", "clients", "documents"}),
    # An approver is not an adviser's manager — they read documents and sign
    # them off. Client files are not theirs to open.
    APPROVER: frozenset({"ask", "documents", "approve_documents"}),
    # erase_clients is admin-only and deliberately separate from
    # approve_documents. Erasure was briefly filed under it, which let an
    # approver destroy records they are not allowed to read — a worse position
    # than either full access or none.
    ADMIN: frozenset({"ask", "clients", "documents", "approve_documents",
                      "erase_clients", "manage_users"}),
}

# The role a trusted local request runs as. On a single-adviser desk the person
# at the keyboard owns the machine and the vault, so the default is admin;
# FORTITUDO_LOCAL_ROLE narrows it where the desk is shared.
def local_role() -> str:
    role = (os.environ.get("FORTITUDO_LOCAL_ROLE") or ADMIN).strip().lower()
    return role if role in ROLES else ADMIN


@dataclass(frozen=True)
class User:
    id: str
    name: str
    role: str = ADVISER
    created_at: str = ""
    disabled_at: str = ""
    note: str = ""

    @property
    def active(self) -> bool:
        return not self.disabled_at

    def may(self, capability: str) -> bool:
        return capability in CAPABILITIES.get(self.role, frozenset())


# The identity of a trusted request when no directory has been set up. Named,
# so that everything downstream can assume there is always somebody to
# attribute an action to, and so the log says "the desk owner" rather than "".
def local_user() -> User:
    return User(id="local", name=os.environ.get("FORTITUDO_LOCAL_NAME")
                or "the desk owner", role=local_role())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    USERS_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(USERS_DB)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def token_sha(token: str) -> str:
    return hashlib.sha256((token or "").encode("utf-8")).hexdigest()


def _row(r: Sequence) -> User:
    return User(id=r[0], name=r[1], role=r[2], created_at=r[4] or "",
                disabled_at=r[5] or "", note=r[6] or "")


def add(name: str, role: str = ADVISER, note: str = "") -> Tuple[Optional[User], str]:
    """Create a user and return them with their token, once.

    The token is shown here and never again, because only its hash is stored.
    Losing it means issuing a new one, which is the correct trade: a directory
    that can print everyone's credentials back is a directory worth stealing.
    """
    name = (name or "").strip()
    if not name:
        return None, "a user needs a name"
    if role not in ROLES:
        return None, f"role must be one of {', '.join(ROLES)}"
    token = secrets.token_urlsafe(32)
    uid = secrets.token_hex(8)
    conn = connect()
    try:
        conn.execute(
            "INSERT INTO users (id, name, role, token_sha, created_at, "
            "disabled_at, note) VALUES (?, ?, ?, ?, ?, '', ?)",
            (uid, name, role, token_sha(token), _now(), note),
        )
        conn.commit()
    finally:
        conn.close()
    return User(id=uid, name=name, role=role, created_at=_now(), note=note), token


def disable(user_id: str) -> Tuple[bool, str]:
    """Revoke access without deleting the person.

    Their name still has to resolve, because it is attached to approvals and
    to logged answers that happened. Deleting the row would leave the audit
    trail pointing at nobody.
    """
    conn = connect()
    try:
        cur = conn.execute("UPDATE users SET disabled_at = ? WHERE id = ? AND "
                           "disabled_at = ''", (_now(), user_id))
        conn.commit()
        if cur.rowcount:
            return True, f"{user_id} disabled"
        return False, "no such active user"
    finally:
        conn.close()


def get(user_id: str) -> Optional[User]:
    conn = connect()
    try:
        r = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return _row(r) if r else None
    finally:
        conn.close()


def everyone(include_disabled: bool = True) -> List[User]:
    conn = connect()
    try:
        rows = conn.execute("SELECT * FROM users ORDER BY created_at").fetchall()
    finally:
        conn.close()
    users = [_row(r) for r in rows]
    return users if include_disabled else [u for u in users if u.active]


def any_users() -> bool:
    """Whether a directory has been set up at all.

    While this is False the desk runs exactly as a single-adviser tool.
    """
    return bool(everyone(include_disabled=False))


def by_token(token: str) -> Optional[User]:
    """Whoever holds this token, if they are still active.

    Compared against stored hashes in constant time. The hash of a wrong token
    is as long as the hash of a right one, so the comparison leaks nothing
    about how much of the token was correct.
    """
    if not token:
        return None
    offered = token_sha(token)
    conn = connect()
    try:
        rows = conn.execute("SELECT * FROM users WHERE disabled_at = ''").fetchall()
    finally:
        conn.close()
    for r in rows:
        if hmac.compare_digest(offered, r[3]):
            return _row(r)
    return None


def identify(peer: str, headers) -> Optional[User]:
    """Who is making this request, or None if nobody can be named.

    This is the seam an FSP would replace with its own directory: everything
    downstream asks for a User and a capability, not for a token.
    """
    import desk_auth
    token = desk_auth.bearer(headers)
    if token:
        found = by_token(token)
        if found:
            return found
        # A valid shared token with no directory behind it is the
        # single-adviser case, reached from off the machine.
        shared = desk_auth.desk_token()
        if shared and hmac.compare_digest(token, shared) and not any_users():
            return local_user()
        return None
    if desk_auth.is_loopback(peer) and not any_users():
        return local_user()
    if desk_auth.is_loopback(peer):
        # A directory exists, so being at the keyboard is no longer an
        # identity. Say so rather than silently acting as the owner.
        return None
    return None


def require(peer, headers, capability: str) -> Tuple[Optional[User], str]:
    """(user, why not). The whole authorisation decision, in one place."""
    user = identify(peer, headers)
    if user is None:
        if any_users():
            return None, ("This desk has named users. Send your own token as: "
                          "Authorization: Bearer <token>")
        return None, "Not authorised."
    if not user.may(capability):
        return None, (f"{user.name} is a {user.role} and may not {capability.replace('_', ' ')}.")
    return user, ""


# Which capability a path needs. One table rather than a check per route: a
# route added later inherits a decision instead of quietly having none.
def capability_for(parts: Sequence[str]) -> str:
    p = list(parts or [])
    if p[:2] == ["api", "register"]:
        # Reading the register is not the same as signing something off.
        return "approve_documents" if len(p) > 2 else "documents"
    # Putting a document into the index is a governance act: in controlled mode
    # it is exactly what the register decides. It is not an ordinary question.
    if p[:2] == ["api", "ingest"]:
        return "documents"
    if p[:2] == ["api", "users"]:
        return "manage_users"
    # Where the client data lives is an answer about the vault.
    if p[:2] == ["api", "residency"]:
        return "clients"
    # Reading what is past its retention date is not the same as destroying it.
    if p[:2] == ["api", "retention"]:
        return "erase_clients" if p[2:3] == ["erase"] else "clients"
    # Both the client list and the client-document blobs. An approver reads
    # product documents; a client's file is not theirs to open.
    #
    # /api/pdf belongs here too, and did not at first: it opens documents out
    # of the client vault by id, so leaving it at "ask" handed an approver the
    # client files that /api/clients refuses them, one route over.
    if p[:2] in (["api", "clients"], ["api", "documents"], ["api", "pdf"]):
        return "clients"
    return "ask"


def render(users: Optional[Sequence[User]] = None) -> str:
    users = everyone() if users is None else users
    if not users:
        return ("No users registered — the desk is running as a single-adviser "
                "tool. Add one with:  python desk_users.py add \"Name\" --role adviser\n")
    width = max(len(u.name) for u in users)
    lines = ["Desk users", "=" * (width + 40)]
    for u in users:
        state = "" if u.active else f"  DISABLED {u.disabled_at[:10]}"
        lines.append(f"  {u.name:<{width}}  {u.role:<9} {u.id}{state}")
    return "\n".join(lines) + "\n"


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="Who may use this desk.")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("list")
    a = sub.add_parser("add")
    a.add_argument("name")
    a.add_argument("--role", default=ADVISER, choices=list(ROLES))
    a.add_argument("--note", default="")
    d = sub.add_parser("disable")
    d.add_argument("user_id")
    args = ap.parse_args()

    if args.cmd == "add":
        user, token = add(args.name, args.role, args.note)
        if user is None:
            print(token)
            raise SystemExit(1)
        print(f"\n  {user.name}  ({user.role})\n  id     {user.id}")
        print(f"  token  {token}\n")
        print("  This token is shown once and is not stored — only its hash is.")
        print("  Give it to them over something private, not over email.\n")
        return
    if args.cmd == "disable":
        ok, msg = disable(args.user_id)
        print(msg)
        raise SystemExit(0 if ok else 1)
    print(render())


if __name__ == "__main__":
    main()
