"""Room registry — which corpus and refusals apply."""
from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet


@dataclass(frozen=True)
class Room:
    id: str
    domain: str
    include_clients: bool
    allow_product_index: bool
    draft_banner: str
    # Can a prompt from this room contain client data? compute.py uses this to
    # decide whether the room may be answered by a model on another machine.
    #
    # `include_clients` is not the same question. It says whether the room
    # attaches a client file on purpose. This says whether client data can end
    # up in the prompt at all — and in an adviser room the adviser's own typed
    # question is enough. Only Craft is False, because a Craft brief is a shop
    # owner's advert and mockup_router refuses one that reads like a client
    # file. Everything else is True, including Learn: a typed lesson can say
    # anything. Assume yes unless the room makes it impossible.
    carries_client_data: bool = True


ROOMS = {
    "fa": Room("fa", "fa", False, True, ""),
    "roa": Room(
        "roa",
        "fa",
        True,
        True,
        "INTERNAL DRAFT — ADVISER REVIEW REQUIRED\n",
    ),
    "voice": Room("voice", "voice", False, False, ""),
    "craft": Room("craft", "craft", False, False, "", carries_client_data=False),
    "drama": Room("drama", "drama", False, False, ""),
    "learn": Room("learn", "learn", False, False, ""),
}

DEFAULT_ROOM = "fa"

ACTIONS = {
    "fa": frozenset({"retrieve", "cite", "meeting_prep"}),
    "roa": frozenset({"retrieve", "cite", "draft_roa", "meeting_prep", "list_gaps"}),
    "voice": frozenset({"draft_social"}),
    "craft": frozenset({"checklist", "mock_page", "quote_band"}),
    "drama": frozenset({"draft_comment", "show_rubric"}),
    "learn": frozenset({"ingest_note"}),
}


def get_room(room_id: str) -> Room:
    return ROOMS.get((room_id or DEFAULT_ROOM).lower(), ROOMS[DEFAULT_ROOM])


def action_allowed(room_id: str, action: str) -> bool:
    allowed: FrozenSet[str] = ACTIONS.get(room_id, ACTIONS[DEFAULT_ROOM])
    return action in allowed
