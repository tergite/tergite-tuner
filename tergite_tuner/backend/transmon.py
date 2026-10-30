# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2023, 2026
# (C) Copyright Liangyu Chen 2023, 2024
# (C) Copyright Abdullah Al Amin 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
import collections
import math
from typing import Any, Hashable, Literal, NamedTuple

import numpy as np
from qcodes import ChannelTuple
from qcodes.instrument import InstrumentBase, InstrumentModule
from qcodes.metadatable import Metadatable
from quantify_scheduler.backends.circuit_to_device import (
    DeviceCompilationConfig,
    OperationCompilationConfig,
)
from quantify_scheduler.device_under_test.transmon_element import (
    BasicTransmonElement,
    ClocksFrequencies,
    DispersiveMeasurement,
    IdlingReset,
    RxyDRAG,
    measurement_factories,
    pulse_factories,
    pulse_library,
)

from tergite_tuner.backend.gates import (
    R12,
    ExtendedClocksFrequencies,
    Spec,
)


class Readout(NamedTuple):
    """A readout operation: the submodule its parameters are in, and its clock's suffix."""

    parameters: str
    clock: str
    should_threshold: bool
    should_label_feedback: bool


READOUTS = {
    "measure_1": Readout("measure", "ro1", True, False),
    "measure_2": Readout("measure", "ro2", False, False),
    "measure_2state_opt": Readout("measure_2state_opt", "ro_2st_opt", True, True),
    "measure_3state_opt": Readout("measure_3state_opt", "ro_3st_opt", False, True),
}


class ExtendedTransmon(BasicTransmonElement):
    def __init__(self, name: str, **kwargs):
        submodules_to_add = {
            "reset": _ExtendedIdlingReset,
            "rxy": _ExtendedRxyDRAG,
            "measure": _ExtendedDispersiveMeasurement,
            "clock_freqs": _ExtendedClocksFrequencies,
            "measure_1": _ExtendedDispersiveMeasurement,
            "measure_2": _ExtendedDispersiveMeasurement,
            "measure_2state_opt": _ExtendedDispersiveMeasurement,
            "measure_3state_opt": _ExtendedDispersiveMeasurement,
            "r12": R12,
            "spec": Spec,
            "extended_clock_freqs": ExtendedClocksFrequencies,
        }

        submodule_data = {
            sub_name: kwargs.pop(sub_name, {}) for sub_name in submodules_to_add.keys()
        }
        super().__init__(name, **kwargs)

        for sub_name, sub_class in submodules_to_add.items():
            self.upsert_submodule(
                sub_name,
                sub_class(
                    parent=self, name=sub_name, **submodule_data.get(sub_name, {})
                ),
            )

    def generate_device_config(self) -> DeviceCompilationConfig:
        elements = self._generate_config()
        operations = elements[self.name]
        for name, readout in READOUTS.items():
            operations[name] = self._get_readout_config(readout)
        operations["r12"] = OperationCompilationConfig(
            factory_func=pulse_factories.rxy_drag_pulse,
            factory_kwargs={
                "amp180": self.r12.ef_amp180(),
                "motzoi": self.r12.ef_motzoi(),
                "port": self.ports.microwave(),
                "clock": f"{self.name}.12",
                "duration": self.r12.ef_duration(),
            },
            gate_info_factory_kwargs=["theta", "phi"],
        )
        operations["spec"] = OperationCompilationConfig(
            factory_func=pulse_factories.rxy_drag_pulse,
            factory_kwargs={
                "spec_amp": self.spec.spec_amp(),
                "spec_ampl_optimal": self.spec.spec_ampl_optimal(),
                "spec_ampl_12_optimal": self.spec.spec_ampl_12_optimal(),
                "spec_duration": self.spec.spec_duration(),
            },
            gate_info_factory_kwargs=["theta", "phi"],
        )
        return DeviceCompilationConfig.model_validate(
            {"elements": elements, "clocks": self._get_clocks(), "edges": {}}
        )

    def _get_clocks(self) -> dict[str, float]:
        return {
            f"{self.name}.01": self.clock_freqs.f01(),
            f"{self.name}.12": self.clock_freqs.f12(),
            f"{self.name}.ro": self.clock_freqs.readout(),
            f"{self.name}.ro1": self.extended_clock_freqs.readout_1(),
            f"{self.name}.ro2": self.extended_clock_freqs.readout_2(),
            f"{self.name}.ro_2st_opt": self.extended_clock_freqs.readout_2state_opt(),
            f"{self.name}.ro_3st_opt": self.extended_clock_freqs.readout_3state_opt(),
        }

    def _get_readout_config(self, readout: "Readout") -> OperationCompilationConfig:
        """A dispersive measurement with ``readout``'s parameters, on its own clock."""
        measure = getattr(self, readout.parameters)
        factory_kwargs = {
            "port": self.ports.readout(),
            "clock": f"{self.name}.{readout.clock}",
            "pulse_type": measure.pulse_type(),
            "pulse_amp": measure.pulse_amp(),
            "pulse_duration": measure.pulse_duration(),
            "acq_delay": measure.acq_delay(),
            "acq_duration": measure.integration_time(),
            "acq_channel": measure.acq_channel(),
            "acq_protocol_default": "SSBIntegrationComplex",
            "reset_clock_phase": measure.reset_clock_phase(),
            "reference_magnitude": pulse_library.ReferenceMagnitude.from_parameter(
                measure.reference_magnitude
            ),
            "acq_weights_a": measure.acq_weights_a(),
            "acq_weights_b": measure.acq_weights_b(),
            "acq_weights_sampling_rate": measure.acq_weights_sampling_rate(),
        }
        if readout.should_threshold:
            factory_kwargs["acq_rotation"] = measure.acq_rotation()
            factory_kwargs["acq_threshold"] = measure.acq_threshold()
        gate_info = ["acq_channel_override", "acq_index", "bin_mode", "acq_protocol"]
        if readout.should_label_feedback:
            gate_info.append("feedback_trigger_label")
        return OperationCompilationConfig(
            factory_func=measurement_factories.dispersive_measurement_transmon,
            factory_kwargs=factory_kwargs,
            gate_info_factory_kwargs=gate_info,
        )

    def upsert_submodule(
        self, name: str, submodule: InstrumentModule | ChannelTuple
    ) -> None:
        """
        Replaces a submodule if it exists or insert is new.

        This is to sidestep using add_submodule which just immediately errs out
        if the submodule already exists.

        Args:
            name: How the submodule will be stored within
                ``instrument.submodules`` and also how it can be
                addressed.
            submodule: The submodule to be stored.

        Raises:
            KeyError: If this instrument already contains a submodule with this
                name.
            TypeError: If the submodule that we are trying to add is
                not an instance of an ``Metadatable`` object.

        """
        if name in self.submodules and isinstance(submodule, Metadatable):
            # remove the submodule
            old_submodule = self.submodules[name]
            if isinstance(old_submodule, collections.abc.Sequence):
                del self._channel_lists[name]
            else:
                del self.instrument_modules[name]

            del self.submodules[name]

        return self.add_submodule(name, submodule)


class _ExtendedRxyDRAG(RxyDRAG):
    # """Allows kwargs explicitly for newer versions of quantify"""

    def __init__(
        self,
        parent: InstrumentBase,
        name: str,
        *,
        amp180: float = math.nan,
        motzoi: float = 0,
        duration: float = 20e-9,
        reference_magnitude_dBm: float = math.nan,
        reference_magnitude_V: float = math.nan,
        reference_magnitude_A: float = math.nan,
        **kwargs: Any,
    ):
        super().__init__(
            parent,
            name,
            amp180=amp180,
            motzoi=motzoi,
            duration=duration,
            reference_magnitude_dBm=reference_magnitude_dBm,
            reference_magnitude_V=reference_magnitude_V,
            reference_magnitude_A=reference_magnitude_A,
        )


class _ExtendedIdlingReset(IdlingReset):
    # """Allows kwargs explicitly for newer versions of quantify"""

    def __init__(
        self,
        parent: InstrumentBase,
        name: str,
        *,
        duration: float = 200e-6,
        **kwargs: Any,
    ) -> None:
        super().__init__(parent=parent, name=name, duration=duration)


class _ExtendedClocksFrequencies(ClocksFrequencies):
    # """Allows kwargs explicitly for newer versions of quantify"""

    def __init__(
        self,
        parent: InstrumentBase,
        name: str,
        *,
        f01: float = math.nan,
        f12: float = math.nan,
        readout: float = math.nan,
        **kwargs: Any,
    ) -> None:
        super().__init__(parent=parent, name=name, f01=f01, f12=f12, readout=readout)


class _ExtendedDispersiveMeasurement(DispersiveMeasurement):
    # """Allows kwargs explicitly for newer versions of quantify"""
    def __init__(
        self,
        parent: InstrumentBase,
        name: str,
        *,
        pulse_type: str = "SquarePulse",
        pulse_amp: float = 0.25,
        pulse_duration: float = 300e-9,
        acq_channel: Hashable = 0,
        acq_delay: float = 0,
        integration_time: float = 1e-6,
        reset_clock_phase: bool = True,
        acq_weights_a: np.ndarray | None = None,
        acq_weights_b: np.ndarray | None = None,
        acq_weights_sampling_rate: float = 1e9,
        acq_weight_type: Literal["SSB", "Numerical"] = "SSB",
        reference_magnitude_dBm: float = math.nan,
        reference_magnitude_V: float = math.nan,
        reference_magnitude_A: float = math.nan,
        acq_rotation: float = 0,
        acq_threshold: float = 0,
        num_points: int = 1,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            parent=parent,
            name=name,
            pulse_type=pulse_type,
            pulse_amp=pulse_amp,
            pulse_duration=pulse_duration,
            acq_channel=acq_channel,
            acq_delay=acq_delay,
            integration_time=integration_time,
            reset_clock_phase=reset_clock_phase,
            acq_weights_a=acq_weights_a,
            acq_weights_b=acq_weights_b,
            acq_weights_sampling_rate=acq_weights_sampling_rate,
            acq_weight_type=acq_weight_type,
            reference_magnitude_dBm=reference_magnitude_dBm,
            reference_magnitude_V=reference_magnitude_V,
            reference_magnitude_A=reference_magnitude_A,
            acq_rotation=acq_rotation,
            acq_threshold=acq_threshold,
            num_points=num_points,
        )
