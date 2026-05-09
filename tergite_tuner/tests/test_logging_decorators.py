# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Tests for :mod:`tergite_tuner.utils.logging.decorators`.

The decorators are tiny but flow-sensitive — they flip an environment
variable that other parts of the package consult to silence logging,
and they MUST clean up even when the wrapped function raises. These
tests pin the contract: the variable is set inside the call, restored
on exit, and consulted via :func:`is_logging_suppressed`.
"""

import os

import pytest

from tergite_tuner.utils.logging.decorators import (
    is_logging_suppressed,
    suppress_logging,
)


@pytest.fixture(autouse=True)
def _clean_suppress_logging_env(monkeypatch):
    """Make sure ``SUPPRESS_LOGGING`` is unset before each test."""
    monkeypatch.delenv("SUPPRESS_LOGGING", raising=False)


def test_is_logging_suppressed_default_false():
    """When the env var isn't set, logging is not suppressed."""
    assert is_logging_suppressed() is False


@pytest.mark.parametrize("truthy", ["True", "true", "TRUE"])
def test_is_logging_suppressed_truthy(monkeypatch, truthy):
    """The strings ``"true"``/``"True"`` (any case) are coerced to ``True``.

    Note: the underlying coercion (:func:`safe_str_to_bool_int_float`)
    only recognises the literal ``"true"``/``"false"`` strings — values
    like ``"1"`` or ``"yes"`` are NOT considered truthy and fall back to
    ``False``.
    """
    monkeypatch.setenv("SUPPRESS_LOGGING", truthy)
    assert is_logging_suppressed() is True


@pytest.mark.parametrize("falsy", ["False", "false", "0", "anything-else"])
def test_is_logging_suppressed_falsy(monkeypatch, falsy):
    """Anything that isn't recognised as ``"true"`` is treated as ``False``."""
    monkeypatch.setenv("SUPPRESS_LOGGING", falsy)
    assert is_logging_suppressed() is False


def test_suppress_logging_sets_and_resets_env():
    """The decorator sets ``SUPPRESS_LOGGING=True`` while the call is on
    the stack, and removes it afterwards."""
    captured = {}

    @suppress_logging
    def fn():
        captured["inside"] = os.environ.get("SUPPRESS_LOGGING")
        return "result"

    assert "SUPPRESS_LOGGING" not in os.environ
    assert fn() == "result"
    assert captured["inside"] == "True"
    assert "SUPPRESS_LOGGING" not in os.environ


def test_suppress_logging_resets_env_on_exception():
    """If the wrapped function raises, ``SUPPRESS_LOGGING`` is still
    cleaned up — that's what the ``finally`` in the decorator buys us."""

    @suppress_logging
    def bad_fn():
        assert os.environ["SUPPRESS_LOGGING"] == "True"
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        bad_fn()

    assert "SUPPRESS_LOGGING" not in os.environ


def test_suppress_logging_passes_args_and_kwargs():
    """``functools.wraps`` is applied — args/kwargs flow through and
    the wrapped name is preserved."""

    @suppress_logging
    def add(a, b, *, factor=1):
        return (a + b) * factor

    assert add(2, 3) == 5
    assert add(2, 3, factor=4) == 20
    assert add.__name__ == "add"
