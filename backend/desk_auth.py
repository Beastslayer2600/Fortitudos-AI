"""Who may talk to the desk.

The desk has always been safe by accident: an http.server bound to loopback
with a CORS allowlist, where the only thing that can reach it is a process on
the same machine. That holds exactly until the moment it is bound to anything
else — and remote access from a phone is on the roadmap, which is the moment
an unauthenticated server holding a FAIS client vault becomes the whole
problem.

The rule here keeps the accident and adds the missing half:

- a request from loopback is trusted, exactly as today, so nothing about
  working on the laptop changes
- a request from anywhere else must present the desk token
- if no token has been set, a non-local request is refused outright rather
  than allowed

That last line is the important one. The failure to avoid is a desk that is
exposed to the network and silently open because nobody got round to setting
a secret. It fails closed.

The public mock pages are the deliberate exception: /m/<slug> exists to be
opened by a stranger with a flyer, and holds no client data.
"""
from __future__ import annotations

import hmac
import os
import secrets
from ipaddress import ip_address
from pathlib import Path
from typing import Optional, Sequence, Tuple

from config import DATA_ROOT

TOKEN_FILE = Path(os.environ.get("FORTITUDO_TOKEN_FILE") or (DATA_ROOT / "desk-token.txt"))

# Routes a stranger is meant to reach. Everything else needs to be local or
# carry the token. Matched on the first path segment.
PUBLIC_PREFIXES: Tuple[str, ...] = ("m",)

# Note there is no "" here. An empty peer address means we could not tell
# where the request came from, and "unknown" is not "local" — treating it as
# local would be a fail-open in the one function whose job is failing closed.
_LOOPBACK = {"127.0.0.1", "::1", "localhost"}


def desk_token() -> str:
    """The shared secret, from the environment or the vault, or "" if unset.

    Kept beside the vault rather than in the repo, so it cannot be committed
    and travels with the data it protects.
    """
    from_env = (os.environ.get("FORTITUDO_DESK_TOKEN") or "").strip()
    if from_env:
        return from_env
    try:
        return TOKEN_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def ensure_token(create: bool = False) -> str:
    """Read the token, optionally minting one on first run."""
    existing = desk_token()
    if existing or not create:
        return existing
    token = secrets.token_urlsafe(32)
    try:
        TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_FILE.write_text(token + "\n", encoding="utf-8")
        try:
            TOKEN_FILE.chmod(0o600)      # best effort; a no-op on Windows
        except OSError:
            pass
    except OSError:
        return ""
    return token


def is_loopback(address: str) -> bool:
    """True when the request came from this machine.

    Anything unparseable is not local. A hostname that merely looks like
    localhost is not a reason to hand over a client vault.
    """
    host = (address or "").strip().strip("[]")
    if not host:
        return False
    if host in _LOOPBACK:
        return True
    try:
        return ip_address(host).is_loopback
    except ValueError:
        return False


def is_public_path(parts: Sequence[str]) -> bool:
    """The mock pages a flyer QR points at. No client data lives there."""
    return bool(parts) and parts[0] in PUBLIC_PREFIXES


def bearer(headers) -> str:
    raw = ""
    try:
        raw = headers.get("Authorization") or ""
    except Exception:
        return ""
    prefix = "bearer "
    return raw[len(prefix):].strip() if raw.lower().startswith(prefix) else ""


def check(peer: str, parts: Sequence[str], headers) -> Tuple[bool, str]:
    """(allowed, why not). The whole policy, in one place so it is testable."""
    if is_public_path(parts):
        return True, ""
    if is_loopback(peer):
        return True, ""

    token = desk_token()
    if not token:
        return False, (
            "This desk is reachable from the network but no token is set, so "
            "it refuses remote requests. On the desk machine set "
            "FORTITUDO_DESK_TOKEN, or start the desk once to have one written "
            f"to {TOKEN_FILE}."
        )
    offered = bearer(headers)
    # Constant time: a fast rejection tells an attacker how much of the token
    # was right.
    if offered and hmac.compare_digest(offered, token):
        return True, ""
    return False, "Not authorised. Send the desk token as: Authorization: Bearer <token>"
