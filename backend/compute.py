"""Which model answers a job, and on which machine.

One CHAT_MODEL for every room was never right. Quoting a benefit table and
writing a <style> block are different jobs, and they want different models —
a general model for the first, a coder model for the second.

Splitting the *host* matters more than splitting the model. A desktop with a
CUDA card is an order of magnitude faster than a laptop running Ollama on CPU,
and FORTITUDO_OLLAMA_HOST already lets the desk point at one. But that sends
every prompt across the LAN as plaintext HTTP, and some of these prompts are
whole client files: the ROA draft path passes the client's documents, and the
filing classifier passes the document it is filing.

So the routing is per job:

- Craft work carries no client data — a lead brief is a shop owner's advert
  and the router refuses one that reads like a client file. It may run on the
  fast box.
- Every other job is assumed to carry client data and is pinned to this
  machine, whatever FORTITUDO_OLLAMA_HOST says. Unknown jobs are pinned too:
  the safe answer is the default, not the fast one.

The pin is overridable, in a variable named after what it costs:
FORTITUDO_ALLOW_REMOTE_CLIENT_DATA=1. Nothing here encrypts anything. It keeps
client data on the machine that holds it unless someone chooses otherwise.

Configure a job with FORTITUDO_<JOB>_MODEL and FORTITUDO_<JOB>_HOST, e.g.

    FORTITUDO_CRAFT_MODEL=qwen2.5-coder:7b
    FORTITUDO_CRAFT_HOST=http://192.168.1.50:11434
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlsplit

from config import CHAT_MODEL
from rooms import ROOMS

# Jobs that reach the model without going through a room.
NON_ROOM_JOBS = {
    "filing": True,    # sort_engine: the document being classified IS a client file
    "sight": True,     # a dropped screenshot can be a client's message
    "mockup": False,   # website_mockup: a brief, never client document text
}

LOOPBACK = {"127.0.0.1", "localhost", "::1", "[::1]"}

ALLOW_REMOTE_CLIENT_DATA = (
    os.environ.get("FORTITUDO_ALLOW_REMOTE_CLIENT_DATA", "").strip().lower()
    in {"1", "true", "yes", "on"}
)


@dataclass(frozen=True)
class Plan:
    job: str
    model: str
    host: str
    carries_client_data: bool
    pinned_local: bool
    why: str


def carries_client_data(job: str) -> bool:
    """Assume yes. Only a job that has been reasoned about may say no."""
    job = (job or "").lower()
    if job in NON_ROOM_JOBS:
        return NON_ROOM_JOBS[job]
    room = ROOMS.get(job)
    if room is not None:
        return room.carries_client_data
    return True


def is_local(host: str) -> bool:
    """True for a host on this machine. Anything unparseable is not local."""
    try:
        parsed = urlsplit(host or "")
    except ValueError:
        return False
    name = (parsed.hostname or "").lower()
    if not name and not parsed.scheme:
        # A bare "127.0.0.1:11434" with no scheme never reaches urlsplit's host.
        name = (host or "").split(":")[0].strip().lower()
    return name in LOOPBACK


def _env(job: str, suffix: str) -> str:
    key = "FORTITUDO_" + (job or "").upper().replace("-", "_") + "_" + suffix
    return (os.environ.get(key) or "").strip()


def resolve(job: str, default_host: str, default_model: str = "") -> Plan:
    """Pick the model and host for one job.

    `default_host` is passed in rather than read here so llm.py stays the one
    place that knows where the desk's Ollama lives.
    """
    job = (job or "").lower()
    model = _env(job, "MODEL") or default_model or CHAT_MODEL
    host = _env(job, "HOST") or default_host
    sensitive = carries_client_data(job)

    if sensitive and not is_local(host) and not ALLOW_REMOTE_CLIENT_DATA:
        return Plan(
            job=job or "(unnamed)", model=model, host="http://127.0.0.1:11434",
            carries_client_data=True, pinned_local=True,
            why=(f"{job or 'this job'} can carry client data, so it stays on this "
                 f"machine instead of {host}. Set "
                 "FORTITUDO_ALLOW_REMOTE_CLIENT_DATA=1 to send it over the network."),
        )
    return Plan(
        job=job or "(unnamed)", model=model, host=host,
        carries_client_data=sensitive, pinned_local=False,
        why=("craft work carries no client data" if not sensitive
             else "client data, and the host is already local"),
    )


def plans(default_host: str) -> list:
    """Every job's routing, for /api/health. Shows what is actually in force."""
    jobs = list(ROOMS.keys()) + sorted(NON_ROOM_JOBS)
    return [resolve(j, default_host) for j in jobs]
