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
    "craft": Room("craft", "craft", False, False, ""),
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
