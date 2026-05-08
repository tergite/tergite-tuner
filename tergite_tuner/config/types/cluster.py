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

"""Loader for the ``cluster_config.json`` file.

Validation is delegated to
:class:`quantify_scheduler.backends.qblox_backend.QbloxHardwareCompilationConfig`,
the canonical pydantic model for the QBlox hardware compilation
configuration. The quantify-scheduler import is deferred until
:meth:`ClusterConfig.from_json` is actually called so that simply
importing this module does not pull in the heavy quantify-scheduler
dependency tree.
"""

import json
from os import PathLike
from typing import Self

from quantify_scheduler.backends.qblox_backend import QbloxHardwareCompilationConfig


class ClusterConfig(QbloxHardwareCompilationConfig):
    """Configuration of the qblox cluster

    This is a thin wrapper that defers validation to
    :class:`quantify_scheduler.backends.qblox_backend.QbloxHardwareCompilationConfig`.
    Calling :meth:`from_json` returns the validated
    ``QbloxHardwareCompilationConfig`` instance directly so that callers
    can use the full quantify-scheduler API on the result.
    """

    @classmethod
    def from_json(cls, file: "PathLike[str]") -> Self:
        """Loads and validates the cluster configuration from a JSON file.

        Args:
            file: path to the ``cluster_config.json`` file

        Returns:
            the parsed and validated ``QbloxHardwareCompilationConfig``
            instance from quantify-scheduler
        """
        with open(file, "r") as f:
            data = json.load(f)
        return cls.model_validate(data)
