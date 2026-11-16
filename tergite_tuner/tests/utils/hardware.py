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
"""Instruments a caller of the tuner would hold open."""

from contextlib import contextmanager

from qblox_instruments import Cluster
from qblox_instruments.types import ClusterType


@contextmanager
def open_dummy_cluster(session):
    """A dummy cluster under the session's cluster name, opened as a caller would; closed on exit."""
    name = get_cluster_name(session)
    modules = session.cluster_config.hardware_description[name].modules
    cluster = Cluster(
        name,
        dummy_cfg={
            str(slot): ClusterType[f"CLUSTER_{module.instrument_type}"]
            for slot, module in modules.items()
        },
    )
    try:
        yield cluster
    finally:
        cluster.close()


def get_cluster_name(session):
    """The name of the session's first cluster."""
    return next(iter(session.cluster_config.hardware_description))
