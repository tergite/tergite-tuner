# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs AB 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

import logging

import pytest

from tergite_tuner.utils.logging import (
    LOG_FILE,
    STATUS_LEVEL,
    ExtendedLogger,
    logger,
    setup_logging,
)


@pytest.fixture(autouse=True)
def restored_handlers():
    handlers = list(logger.handlers)
    yield
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    for handler in handlers:
        logger.addHandler(handler)


def test_setting_up_again_replaces_the_handlers(tmp_path):
    setup_logging(STATUS_LEVEL, logging.DEBUG, tmp_path / "first")
    setup_logging(STATUS_LEVEL, logging.DEBUG)

    assert [type(handler) for handler in logger.handlers] == [logging.StreamHandler]


def test_the_log_file_keeps_its_own_level(tmp_path):
    setup_logging(logging.WARNING, STATUS_LEVEL, tmp_path)

    logger.info("left out")
    logger.status("kept")
    for handler in logger.handlers:
        handler.flush()

    text = (tmp_path / LOG_FILE).read_text()
    assert "STATUS - kept" in text
    assert "left out" not in text


def test_other_loggers_keep_the_default_class():
    assert logging.getLoggerClass() is not ExtendedLogger
    assert isinstance(logger, ExtendedLogger)
