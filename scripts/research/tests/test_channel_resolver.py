"""Tests for channel input parsing and normalization."""
from __future__ import annotations

import pytest

from scripts.research.channel_resolver import (
    ChannelInput,
    normalize_for_api,
    parse_channel_input,
)


class TestParseChannelInput:
    def test_bare_handle(self) -> None:
        result = parse_channel_input("@mrbeast")
        assert result == ChannelInput(kind="handle", value="@mrbeast")

    def test_raw_channel_id(self) -> None:
        result = parse_channel_input("UCX6OQ3DkcsbYNE6H8uQQuVA")
        assert result == ChannelInput(kind="id", value="UCX6OQ3DkcsbYNE6H8uQQuVA")

    def test_url_with_handle(self) -> None:
        result = parse_channel_input("https://www.youtube.com/@mrbeast")
        assert result == ChannelInput(kind="url_handle", value="@mrbeast")

    def test_url_with_channel_id(self) -> None:
        result = parse_channel_input("https://www.youtube.com/channel/UCX6OQ3DkcsbYNE6H8uQQuVA")
        assert result == ChannelInput(kind="url_id", value="UCX6OQ3DkcsbYNE6H8uQQuVA")

    def test_url_with_trailing_slash(self) -> None:
        result = parse_channel_input("https://www.youtube.com/@mrbeast/")
        assert result == ChannelInput(kind="url_handle", value="@mrbeast")

    def test_whitespace_is_stripped(self) -> None:
        result = parse_channel_input("  @mrbeast  ")
        assert result == ChannelInput(kind="handle", value="@mrbeast")

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError):
            parse_channel_input("")

    def test_gibberish_raises(self) -> None:
        with pytest.raises(ValueError):
            parse_channel_input("not-a-handle-or-url")


class TestNormalizeForApi:
    def test_handle_becomes_forhandle(self) -> None:
        ci = ChannelInput(kind="handle", value="@mrbeast")
        assert normalize_for_api(ci) == ("forHandle", "@mrbeast")

    def test_url_handle_becomes_forhandle(self) -> None:
        ci = ChannelInput(kind="url_handle", value="@mrbeast")
        assert normalize_for_api(ci) == ("forHandle", "@mrbeast")

    def test_id_becomes_id(self) -> None:
        ci = ChannelInput(kind="id", value="UCX6OQ3DkcsbYNE6H8uQQuVA")
        assert normalize_for_api(ci) == ("id", "UCX6OQ3DkcsbYNE6H8uQQuVA")

    def test_url_id_becomes_id(self) -> None:
        ci = ChannelInput(kind="url_id", value="UCX6OQ3DkcsbYNE6H8uQQuVA")
        assert normalize_for_api(ci) == ("id", "UCX6OQ3DkcsbYNE6H8uQQuVA")
