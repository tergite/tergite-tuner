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
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

from qcodes.instrument import InstrumentBase
from qcodes.parameters import Parameter
from quantify_scheduler.device_under_test.quantum_device import QuantumDevice
from quantify_scheduler.json_utils import SchedulerJSONEncoder

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

    for coupler in _get_couplers_among(couplers or [], qubits):
        edge = _load_coupler(
            session.state.get_record("couplers", coupler), coupler=coupler
        )
        device.add_edge(edge)

    device.hardware_config(session.cluster_config)
    return device


@contextmanager
def open_node_device(
    name: str,
    qubits: list[str],
    couplers: list[str],
    session: "SessionContext",
    host_device: QuantumDevice | None = None,
) -> Iterator[QuantumDevice]:
    """A node's quantum device of ``qubits`` and the couplers among them, set from the session's state.

    Without ``host_device``, the tuner builds the elements and closes them when the context
    ends. With one, the node runs on the host's own elements: each is set from the state
    while the context lasts, then set back as it was, however the context ends. The host's
    elements are never closed.

    Args:
        name: the device's name, the node's.
        qubits: the qubits to measure.
        couplers: the session's couplers; only those between two of ``qubits`` are added.
        session: the session whose state the elements are set from.
        host_device: the caller's quantum device, whose elements to run on.

    Yields:
        The node's quantum device.

    Raises:
        KeyError: ``host_device`` lacks one of the qubits or couplers.
        TypeError: one of its elements is not an ``ExtendedTransmon`` or
            ``ExtendedCompositeSquareEdge``, or a subclass.
    """
    if host_device is None:
        device = configure_device(name, qubits, couplers, session)
        try:
            yield device
        finally:
            close_device_resources(device)
        return

    device = QuantumDevice(name)
    settings: list[tuple[Parameter, Any]] = []
    try:
        for channel, qubit in enumerate(qubits):
            transmon = host_device.get_element(qubit)
            _raise_if_not_a(transmon, ExtendedTransmon)
            settings.extend(_get_settings(transmon))
            _set_transmon(
                transmon, session.state.get_record("transmons", qubit), channel
            )
            device.add_element(transmon)

        for coupler in _get_couplers_among(couplers or [], qubits):
            edge = host_device.get_edge(coupler)
            _raise_if_not_a(edge, ExtendedCompositeSquareEdge)
            settings.extend(_get_settings(edge))
            _set_coupler(edge, session.state.get_record("couplers", coupler), coupler)
            device.add_edge(edge)

        device.hardware_config(session.cluster_config)
        yield device
    finally:
        for parameter, value in settings:
            parameter.set(value)
        device.close()


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


def _get_couplers_among(couplers: list[str], qubits: list[str]) -> list[str]:
    """The couplers both of whose qubits are among ``qubits``: an edge of a qubit the
    device lacks would fail its compilation."""
    return [
        coupler
        for coupler in couplers
        if all(qubit in qubits for qubit in coupler.split("_"))
    ]


def _load_transmon(
    record: Mapping[str, Any], qubit: str, channel: int
) -> ExtendedTransmon:
    """The qubit's transmon, with its record's nested sections over the defaults, measuring on ``channel``."""
    transmon = ExtendedTransmon(qubit)
    _set_transmon(transmon, record, channel)
    return transmon


def _load_coupler(
    record: Mapping[str, Any], coupler: str
) -> ExtendedCompositeSquareEdge:
    """The edge of ``coupler`` (``qXX_qXX``), with its record's values."""
    control, target = coupler.split(sep="_")
    coupler_edge = ExtendedCompositeSquareEdge(
        parent_element_name=control, child_element_name=target
    )
    _set_coupler(coupler_edge, record, coupler)
    return coupler_edge


def _set_transmon(
    transmon: ExtendedTransmon, record: Mapping[str, Any], channel: int
) -> None:
    """Sets ``transmon``'s submodules from its record's nested sections, measuring on ``channel``."""
    for name, submodule in transmon.submodules.items():
        section = record.get(name)
        values = dict(section) if isinstance(section, Mapping) else {}
        if "measure" in name:
            values["acq_channel"] = channel
        for key, value in values.items():
            if key in submodule.parameters:
                submodule.parameters[key](value)


def _set_coupler(
    coupler_edge: ExtendedCompositeSquareEdge, record: Mapping[str, Any], coupler: str
) -> None:
    """Sets the edge of ``coupler`` (``qXX_qXX``) from its record's values."""
    control, _ = coupler.split(sep="_")

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


def _get_settings(instrument: InstrumentBase) -> list[tuple[Parameter, Any]]:
    """Each settable parameter of ``instrument`` and of its submodules, with its value."""
    settings = [
        (parameter, parameter.get())
        for parameter in instrument.parameters.values()
        if parameter.settable and parameter.gettable
    ]
    for submodule in instrument.submodules.values():
        if isinstance(submodule, InstrumentBase):
            settings.extend(_get_settings(submodule))
    return settings


def _raise_if_not_a(element: InstrumentBase, element_type: type) -> None:
    """Raises ``TypeError`` unless ``element`` is an ``element_type``."""
    if not isinstance(element, element_type):
        raise TypeError(
            f"{element.name} is a {type(element).__name__}; the tuner runs only on "
            f"{element_type.__name__} and its subclasses"
        )
