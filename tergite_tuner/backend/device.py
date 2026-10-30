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
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

from quantify_scheduler.device_under_test.quantum_device import QuantumDevice
from quantify_scheduler.json_utils import SchedulerJSONDecoder, SchedulerJSONEncoder

from tergite_tuner.backend import transmon as transmon_module
from tergite_tuner.backend.edge import ExtendedCompositeSquareEdge
from tergite_tuner.backend.transmon import ExtendedTransmon
from tergite_tuner.utils.logging import logger

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
        transmon = _load_transmon(
            session.state.get_record("transmons", qubit), qubit=qubit, channel=channel
        )
        device.add_element(transmon)

    if couplers is not None:
        for coupler in couplers:
            edge = _load_coupler(
                session.state.get_record("couplers", coupler), coupler=coupler
            )
            device.add_edge(edge)

    device.hardware_config(session.cluster_config)
    return device


def close_device_resources(device: QuantumDevice):
    """
    closes the Quantum Device and all the attached BasicTransmonElement
    and BasicCompositeEdge objsects so they become available for the next node.
    Note that closing the QuantumDevice alone is not enough
    """
    for qubit in device.elements():
        transmon = device.get_element(qubit)
        transmon.close()
    couplers = device.edges()
    if couplers is not None:
        for coupler in couplers:
            edge = device.get_edge(coupler)
            edge.close()

    device.close()


def save_serial_device(device: QuantumDevice, data_path: str) -> None:
    """
    decode the device object and then parse its data element by element
    to populate the serial device dictionary which is saved as Json
    """
    name = device.name
    serialized_device = json.dumps(device, cls=SchedulerJSONEncoder)
    decoded_device = json.loads(serialized_device)
    serial_device = {}
    for element, element_config in decoded_device["data"]["elements"].items():
        serial_config = json.loads(element_config)
        serial_device[element] = serial_config

    for element, element_config in decoded_device["data"]["edges"].items():
        serial_config = json.loads(element_config)
        serial_device[element] = serial_config

    Path(data_path).mkdir(parents=True, exist_ok=True)
    with open(f"{data_path}/{name}.json", "w") as f:
        json.dump(serial_device, f, indent=4)


def _load_transmon(
    record: Mapping[str, Any], qubit: str, channel: int
) -> ExtendedTransmon:
    """The qubit's transmon, with its record's nested sections over the defaults, measuring on ``channel``."""
    transmon = ExtendedTransmon(qubit)
    transmon_config = {k: v for k, v in record.items() if isinstance(v, dict)}

    # get the transmon template in dictionary form
    serialized_transmon = json.dumps(transmon, cls=SchedulerJSONEncoder)
    decoded_transmon = json.loads(serialized_transmon)
    decoded_transmon["name"] = qubit

    for k, v in decoded_transmon["data"].items():
        if isinstance(v, dict) and k in transmon_config:
            v.update(transmon_config[k])
        if "measure" in k:
            v.update({"acq_channel": channel})

    encoded_transmon = json.dumps(decoded_transmon)

    # free the transmon
    transmon.close()

    # create a transmon with the same name but with updated config
    transmon = json.loads(
        encoded_transmon, cls=SchedulerJSONDecoder, modules=[transmon_module]
    )

    return transmon


def _load_coupler(
    record: Mapping[str, Any], coupler: str
) -> ExtendedCompositeSquareEdge:
    """The edge of ``coupler`` (``qXX_qXX``), with its record's values."""
    control, target = coupler.split(sep="_")
    coupler_edge = ExtendedCompositeSquareEdge(
        parent_element_name=control, child_element_name=target
    )

    attrs_map = {
        "cz_pulse_frequency": coupler_edge.clock_freqs.cz_freq,
        "cz_pulse_amplitude": coupler_edge.cz.square_amp,
        "cz_pulse_duration": coupler_edge.cz.square_duration,
        "cz_half_duration": coupler_edge.cz.half_square_duration,
        "cz_pulse_width": coupler_edge.cz.cz_width,
        "parking_current": coupler_edge.coupler_parameters.parking_current,
        "initial_parking_current": coupler_edge.coupler_parameters.parking_current,
        "cz_phase_path": coupler_edge.coupler_parameters.phase_path,
    }

    for k, param in attrs_map.items():
        try:
            param(record[k])
        except (KeyError, TypeError):
            logger.warning(
                f"{k} is not in the device state. Ignore this for single qubit nodes"
            )

    try:
        if control == record["target_qubit"]:
            logger.info(f"Reading Target Qubit: {control}")
            coupler_edge.cz.parent_phase_correction(record["cz_dynamic_target"])
            coupler_edge.cz.child_phase_correction(record["cz_dynamic_control"])

        elif control == record["control_qubit"]:
            logger.info(f"Reading Control Qubit: {control}")
            coupler_edge.cz.parent_phase_correction(record["cz_dynamic_control"])
            coupler_edge.cz.child_phase_correction(record["cz_dynamic_target"])
        else:
            raise ValueError("Control - Target types not defined")
    except (KeyError, ValueError, TypeError):
        logger.warning("Invalid Control and Target")

    return coupler_edge
