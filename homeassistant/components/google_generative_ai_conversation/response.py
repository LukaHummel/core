"""Schema and validation for structured conversation responses."""

import json
from typing import TypedDict


class SimpleCard(TypedDict):
    """Display content for a native intent card."""

    title: str
    content: str


RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "speech": {"type": "STRING"},
        "card": {
            "type": "OBJECT",
            "nullable": True,
            "properties": {
                "title": {"type": "STRING"},
                "content": {"type": "STRING"},
            },
            "required": ["title", "content"],
        },
    },
    "required": ["speech", "card"],
}


def parse_response(text: str | None) -> tuple[str, SimpleCard | None]:
    """Validate before modifying any part of the intent response."""
    if not text:
        raise ValueError("Empty structured response")
    data = json.loads(text)
    if not isinstance(data, dict) or set(data) != {"speech", "card"}:
        raise ValueError("Invalid structured response")
    speech = data["speech"]
    if not isinstance(speech, str) or not speech.strip() or len(speech) > 2000:
        raise ValueError("Invalid speech")
    card = data["card"]
    if card is not None:
        if not isinstance(card, dict) or set(card) != {"title", "content"}:
            raise ValueError("Invalid card")
        for key, limit in (("title", 200), ("content", 20000)):
            if (
                not isinstance(card[key], str)
                or not card[key].strip()
                or len(card[key]) > limit
            ):
                raise ValueError("Invalid card text")
        return speech, SimpleCard(title=card["title"], content=card["content"])
    return speech, None
