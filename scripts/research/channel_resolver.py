"""Parse and normalize YouTube channel inputs (handle / URL / raw ID)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

ChannelKind = Literal["handle", "id", "url_handle", "url_id"]

_HANDLE_RE = re.compile(r"^@[\w.\-]{1,60}$")
_ID_RE = re.compile(r"^UC[\w\-]{22}$")
_URL_HANDLE_RE = re.compile(r"^https?://(?:www\.)?youtube\.com/(@[\w.\-]{1,60})/?$")
_URL_ID_RE = re.compile(r"^https?://(?:www\.)?youtube\.com/channel/(UC[\w\-]{22})/?$")


@dataclass(frozen=True)
class ChannelInput:
    kind: ChannelKind
    value: str


def parse_channel_input(raw: str) -> ChannelInput:
    """Detect the shape of a channel input string and normalize it.

    Raises ValueError if the input matches no known format.
    """
    if not isinstance(raw, str):
        raise ValueError(f"channel input must be a string, got {type(raw).__name__}")
    s = raw.strip()
    if not s:
        raise ValueError("channel input is empty")

    if m := _URL_HANDLE_RE.match(s):
        return ChannelInput(kind="url_handle", value=m.group(1))
    if m := _URL_ID_RE.match(s):
        return ChannelInput(kind="url_id", value=m.group(1))
    if _HANDLE_RE.match(s):
        return ChannelInput(kind="handle", value=s)
    if _ID_RE.match(s):
        return ChannelInput(kind="id", value=s)

    raise ValueError(
        f"unrecognized channel input: {raw!r}. "
        "expected @handle, UC-prefixed channel id, or a youtube.com URL."
    )


def normalize_for_api(parsed: ChannelInput) -> tuple[str, str]:
    """Return the (param_name, param_value) pair for the YouTube Data API channels.list call."""
    if parsed.kind in ("handle", "url_handle"):
        return ("forHandle", parsed.value)
    return ("id", parsed.value)
