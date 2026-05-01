# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs 2024
# (C) Copyright Michele Faucci Giannelli 2025
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

import os.path
from datetime import datetime
from functools import cached_property
from ipaddress import IPv4Address
from typing import List, Optional, Self

from pydantic import BaseModel, PrivateAttr, computed_field, model_validator

from tergite_autocalibration.lib.nodes import NodeEnum
from tergite_autocalibration.utils.dto.enums import ApplicationStatus, MeasurementMode


class SessionContext(BaseModel):
    """context for the current run session

    Attributes:
        cluster_ip: the IP address of the Qblox cluster being used
        target_node: the calibration node on which to stop
        qubits: the list of names of the qubits being calibrated
        couplers: the list of names of the couplers being calibrated
        name: the name of this session; it defaults to the target node name in lower case
        data_dir: the path to the folder where the calibration data is stored
        log_dir: the path to the folder where the log files are stored
        cluster_mode: the measurement mode in which the Qblox cluster is running
        cluster_timeout: The timeout used for waiting for the experiment to complete
            when retrieving acquisitions from the Qblox cluster.
        user_samplespace: the user samplespace for this session
        id: the identifier of this session
        _timestamp: the timestamp of when this session started
    """

    cluster_ip: Optional["IPv4Address"] = None
    target_node: Optional[NodeEnum] = None
    qubits: List[str] = []
    couplers: Optional[List[str]] = None
    name: str = None
    data_dir: Optional[str] = None
    log_dir: str = None
    cluster_mode: "MeasurementMode" = MeasurementMode.real
    cluster_timeout: int = 222
    user_samplespace: dict = {}
    _timestamp: datetime = PrivateAttr(default_factory=datetime.now)

    @model_validator(mode="after")
    def update_attrs(self) -> Self:
        """A validator that computes any attributes that depend on other attributes"""
        if self.name is None and isinstance(self.target_node, NodeEnum):
            self.name = self.target_node.to_string()

        if self.log_dir is None:
            self.log_dir = os.path.join(
                self._timestamp.strftime("%Y-%m-%d"),
                f"{self._timestamp.strftime('%H-%M-%S')}_{self.name}-{str(ApplicationStatus.ACTIVE.value)}",
            )
        return self

    @computed_field
    @cached_property
    def id(self) -> str:
        """Identifier of the session"""
        return f"{self._timestamp.strftime('%Y-%m-%d--%H-%M-%S')}--tac-run-id"
