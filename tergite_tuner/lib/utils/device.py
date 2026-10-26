# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2024
# (C) Copyright Chalmers Next Labs 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

import json
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping

from qblox_scheduler import QuantumDevice
from qblox_scheduler.structure.model import SchedulerSubmodule

from tergite_tuner.storage.redis import RedisStore
from tergite_tuner.utils.logging import logger
from tergite_tuner.utils.types.extended_coupler_edge import ExtendedCompositeSquareEdge
from tergite_tuner.utils.types.extended_transmon import ExtendedTransmon

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext


def configure_device(
    name: str,
    qubits: list[str],
    couplers: list[str],
    session: "SessionContext",
) -> QuantumDevice:
    device = QuantumDevice(name)
    for channel, qubit in enumerate(qubits):
        transmon = _load_transmon_from_redis(
            session.redis_store, qubit=qubit, channel=channel
        )
        device.add_element(transmon)

    if couplers is not None:
        for coupler in couplers:
            edge = _load_coupler_from_redis(session.redis_store, coupler=coupler)
            device.add_edge(edge)

    device.hardware_config = session.cluster_config
    return device


def save_serial_device(device: QuantumDevice, data_path: str) -> None:
    """Saves the parameters of each element and edge of the device as Json"""
    serial_device = {
        name: component.model_dump(mode="json")
        for name, component in {**device.elements, **device.edges}.items()
    }

    Path(data_path).mkdir(parents=True, exist_ok=True)
    with open(f"{data_path}/{device.name}.json", "w") as f:
        json.dump(serial_device, f, indent=4)


def _load_transmon_from_redis(
    redis_store: RedisStore,
    qubit: str,
    channel: int,
) -> ExtendedTransmon:
    """Initializes the transmon using data from redis

    Args:
        redis_store: the Redis store
        qubit: the qubit name
        channel: the channel number

    Returns:
        the ExtendedTransmon instance as loaded from redis
    """
    transmon = ExtendedTransmon(qubit)
    redis_data = {}
    with suppress(KeyError):
        # ignore if key does not exist
        redis_data = redis_store.find_one(collection="transmons", pk=qubit)

    for name, submodule in transmon.submodules.items():
        _set_parameters(submodule, redis_data.get(name, {}))
        if "measure" in name:
            submodule.acq_label = channel

    return transmon


def _load_coupler_from_redis(
    redis_store: RedisStore, coupler: str
) -> ExtendedCompositeSquareEdge:
    """Loads the coupler from redis store

    Args:
        coupler: the coupler name of format qXX_qXX
        redis_store: the RedisStore instance

    Returns:
        the ExtendedCompositeSquareEdge instance
    """
    control, target = coupler.split(sep="_")
    coupler_edge = ExtendedCompositeSquareEdge(
        parent_element_name=control, child_element_name=target
    )
    redis_data = {}
    with suppress(KeyError):
        # ignore if the key does not exist
        redis_data = redis_store.find_one(collection="couplers", pk=coupler)

    attrs_map = {
        "cz_pulse_frequency": (coupler_edge.clock_freqs, "cz_freq"),
        "cz_pulse_amplitude": (coupler_edge.cz, "square_amp"),
        "cz_pulse_duration": (coupler_edge.cz, "square_duration"),
        "cz_half_duration": (coupler_edge.cz, "half_square_duration"),
        "cz_pulse_width": (coupler_edge.cz, "cz_width"),
        "parking_current": (coupler_edge.coupler_parameters, "parking_current"),
        "initial_parking_current": (
            coupler_edge.coupler_parameters,
            "parking_current",
        ),
        "cz_phase_path": (coupler_edge.coupler_parameters, "phase_path"),
    }

    for k, (submodule, parameter) in attrs_map.items():
        try:
            setattr(submodule, parameter, redis_data[k])
        except (KeyError, ValueError):
            logger.warning(
                f"{k} is not present in redis. Ignore this for single qubit nodes"
            )

    try:
        if control == redis_data["target_qubit"]:
            logger.info(f"Reading Target Qubit from Redis: {control}")
            coupler_edge.cz.parent_phase_correction = redis_data["cz_dynamic_target"]
            coupler_edge.cz.child_phase_correction = redis_data["cz_dynamic_control"]

        elif control == redis_data["control_qubit"]:
            logger.info(f"Reading Control Qubit from Redis: {control}")
            coupler_edge.cz.parent_phase_correction = redis_data["cz_dynamic_control"]
            coupler_edge.cz.child_phase_correction = redis_data["cz_dynamic_target"]
        else:
            raise ValueError("Control - Target types not defined")
    except (KeyError, ValueError, TypeError):
        logger.warning("Invalid Control and Target")

    return coupler_edge


def _set_parameters(submodule: SchedulerSubmodule, values: Mapping[str, Any]) -> None:
    """Sets the submodule's parameters found in ``values``, keeping the default of any invalid one."""
    for name, value in values.items():
        if name not in submodule.parameters:
            continue
        try:
            setattr(submodule, name, value)
        except ValueError as exp:
            logger.warning(f"{submodule.name}:{name} keeps its default: {exp}")
