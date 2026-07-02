from __future__ import annotations

from unittest.mock import MagicMock, patch, call

import pytest

from scripts.common.errors import (
    ApiError,
    QuotaExceeded,
    RefusedByPolicy,
    TransientError,
    retry_on_transient,
)


def test_exception_hierarchy():
    assert issubclass(TransientError, ApiError)
    assert issubclass(QuotaExceeded, ApiError)
    assert issubclass(RefusedByPolicy, ApiError)


def test_returns_value_when_fn_succeeds():
    fn = MagicMock(return_value="ok")
    with patch("scripts.common.errors.time.sleep") as sleep:
        assert retry_on_transient(fn) == "ok"
    assert fn.call_count == 1
    assert sleep.call_count == 0


def test_retries_transient_then_succeeds():
    fn = MagicMock(side_effect=[TransientError("x"), TransientError("x"), "ok"])
    with patch("scripts.common.errors.time.sleep") as sleep:
        assert retry_on_transient(fn) == "ok"
    assert fn.call_count == 3
    assert sleep.call_count == 2
    sleep.assert_has_calls([call(1.0), call(3.0)])


def test_reraises_after_exhausting_retries():
    fn = MagicMock(side_effect=TransientError("boom"))
    with patch("scripts.common.errors.time.sleep") as sleep:
        with pytest.raises(TransientError):
            retry_on_transient(fn, retries=3)
    assert sleep.call_count == 3


def test_non_transient_propagates_immediately():
    fn = MagicMock(side_effect=QuotaExceeded("nope"))
    with patch("scripts.common.errors.time.sleep") as sleep:
        with pytest.raises(QuotaExceeded):
            retry_on_transient(fn)
    assert fn.call_count == 1
    assert sleep.call_count == 0
