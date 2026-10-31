# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2023
# (C) Copyright Chalmers Next Labs AB 2024, 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

import logging
from pathlib import Path

# between INFO and WARNING, so the tuner's progress shows without third-party libraries' INFO
STATUS_LEVEL = 25
LOG_FILE = "tergite_tuner.log"
FORMAT = "%(asctime)s - %(levelname)s - %(message)s"


class ExtendedLogger(logging.Logger):
    """A logger with a ``status`` level, between INFO and WARNING."""

    def status(self, message: str, *args: object, **kwargs: object) -> None:
        """Logs ``message`` at the ``STATUS`` level, as ``info`` logs at INFO.

        Args:
            message: the message, formatted with ``args``.
            *args: the message's formatting arguments.
            **kwargs: what ``logging.Logger.log`` takes, such as ``exc_info``.
        """
        if self.isEnabledFor(STATUS_LEVEL):
            self._log(STATUS_LEVEL, message, args, **kwargs)


def setup_logging(
    stdout_level: int, file_level: int, log_dir: Path | None = None
) -> None:
    """Logs to the console at ``stdout_level``, and to ``log_dir``'s log file at ``file_level``.

    Replaces the handlers an earlier call added, as each run calls it.

    Args:
        stdout_level: the console's lowest level.
        file_level: the log file's lowest level.
        log_dir: the folder of the log file; no file is written if None.
    """
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter(FORMAT, datefmt="%H:%M:%S"))
    console.setLevel(stdout_level)
    logger.addHandler(console)
    if log_dir is not None:
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        file = logging.FileHandler(Path(log_dir) / LOG_FILE)
        file.setFormatter(logging.Formatter(FORMAT))
        file.setLevel(file_level)
        logger.addHandler(file)


logging.addLevelName(STATUS_LEVEL, "STATUS")
# made with ExtendedLogger without leaving it the class of every logger made after
_logger_class = logging.getLoggerClass()
logging.setLoggerClass(ExtendedLogger)
logger: ExtendedLogger = logging.getLogger(__name__)
logging.setLoggerClass(_logger_class)
# the handlers filter by level, so the logger passes everything to them
logger.setLevel(logging.DEBUG)
