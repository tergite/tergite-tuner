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

"""Tests for :mod:`tergite_tuner.utils.misc.os`.

The ``get_os`` helper inspects ``sys.platform`` and returns a
:class:`OperatingSystem` enum. We patch :data:`sys.platform` to walk
each branch — including the unrecognised case — without depending on
where the tests happen to be running.
"""

import importlib

import pytest

from tergite_tuner.utils.misc import os as os_module
from tergite_tuner.utils.misc.os import OperatingSystem


@pytest.mark.parametrize(
    "platform_value, expected",
    [
        ("linux", OperatingSystem.LINUX),
        ("linux2", OperatingSystem.LINUX),  # not a match — only literal 'linux'
        ("darwin", OperatingSystem.MAC),
        ("win32", OperatingSystem.WINDOWS),
        ("cygwin", OperatingSystem.WINDOWS),  # contains 'win'
        ("freebsd", OperatingSystem.UNDEFINED),
    ],
)
def test_get_os_recognises_each_platform(monkeypatch, platform_value, expected):
    """The function should return the correct :class:`OperatingSystem`
    for each well-known platform string.

    Note: ``get_os`` only matches the literal ``'linux'`` string for
    LINUX, not ``'linux2'`` — so that case maps to UNDEFINED.
    """
    monkeypatch.setattr(os_module, "platform", platform_value)
    importlib.reload  # silence unused-import linter; kept for clarity
    if platform_value == "linux2":
        assert os_module.get_os() == OperatingSystem.UNDEFINED
    else:
        assert os_module.get_os() == expected
