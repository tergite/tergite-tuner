# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2023, 2026
# (C) Copyright Liangyu Chen 2023, 2024
# (C) Copyright Abdullah Al Amin 2026
# (C) Copyright Chalmers Next Labs 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
from typing import Literal

from qblox_scheduler.backends.graph_compilation import (
    DeviceCompilationConfig,
    OperationCompilationConfig,
)
from qblox_scheduler.device_under_test.transmon_element import (
    ReferenceMagnitude,  # pydantic resolves the submodules' forward references here
)
from qblox_scheduler.device_under_test.transmon_element import (
    BasicTransmonElement,
    DispersiveMeasurement,
    RxyDRAG,
)
from qblox_scheduler.operations import (
    measurement_factories,
    pulse_factories,
    pulse_library,
)
from qblox_scheduler.structure.model import Numbers, Parameter

from tergite_tuner.utils.types.extended_gates import (
    R12,
    ExtendedClocksFrequencies,
    Spec,
)
from tergite_tuner.utils.types.extended_pulse_factories import motzoi_to_beta

# the operations BasicTransmonElement compiles to rxy_drag_pulse
_DRAG_OPERATIONS = ("Rxy", "X", "X90", "Y", "Y90")


class ExtendedRxyDRAG(RxyDRAG):
    # quantify-scheduler's D_amp of the DRAG pulse; it replaces the inherited beta
    motzoi: float = Parameter(
        initial_value=0.0,
        vals=Numbers(min_value=-1, max_value=1),
    )


class ExtendedTransmon(BasicTransmonElement):
    element_type: Literal["ExtendedTransmon"] = "ExtendedTransmon"
    rxy: ExtendedRxyDRAG
    measure_1: DispersiveMeasurement
    measure_2: DispersiveMeasurement
    measure_2state_opt: DispersiveMeasurement
    measure_3state_opt: DispersiveMeasurement
    r12: R12
    spec: Spec
    extended_clock_freqs: ExtendedClocksFrequencies

    def generate_device_config(self) -> DeviceCompilationConfig:
        elements = self._generate_config()
        operations = elements[self.name]

        beta = motzoi_to_beta(self.rxy.motzoi, self.rxy.duration)
        for name in _DRAG_OPERATIONS:
            operations[name].factory_kwargs["beta"] = beta

        # measure_1 and measure_2 read out with the measure parameters, on their own clocks
        operations["measure_1"] = self._measure_config(self.measure, "ro1")
        operations["measure_2"] = self._measure_config(
            self.measure, "ro2", with_threshold=False
        )
        operations["measure_2state_opt"] = self._measure_config(
            self.measure_2state_opt, "ro_2st_opt"
        )
        operations["measure_3state_opt"] = self._measure_config(
            self.measure_3state_opt, "ro_3st_opt", with_threshold=False
        )
        operations["r12"] = OperationCompilationConfig(
            factory_func=pulse_factories.rxy_drag_pulse,
            factory_kwargs={
                "amp180": self.r12.ef_amp180,
                "beta": motzoi_to_beta(self.r12.ef_motzoi, self.r12.ef_duration),
                "port": self.ports.microwave,
                "clock": f"{self.name}.12",
                "duration": self.r12.ef_duration,
            },
            gate_info_factory_kwargs=["theta", "phi"],
        )
        operations["spec"] = OperationCompilationConfig(
            factory_func=pulse_factories.rxy_drag_pulse,
            factory_kwargs={
                "spec_amp": self.spec.spec_amp,
                "spec_ampl_optimal": self.spec.spec_ampl_optimal,
                "spec_ampl_12_optimal": self.spec.spec_ampl_12_optimal,
                "spec_duration": self.spec.spec_duration,
            },
            gate_info_factory_kwargs=["theta", "phi"],
        )

        return DeviceCompilationConfig.model_validate(
            {
                "elements": elements,
                "clocks": {
                    f"{self.name}.01": self.clock_freqs.f01,
                    f"{self.name}.12": self.clock_freqs.f12,
                    f"{self.name}.ro": self.clock_freqs.readout,
                    f"{self.name}.ro1": self.extended_clock_freqs.readout_1,
                    f"{self.name}.ro2": self.extended_clock_freqs.readout_2,
                    f"{self.name}.ro_2st_opt": self.extended_clock_freqs.readout_2state_opt,
                    f"{self.name}.ro_3st_opt": self.extended_clock_freqs.readout_3state_opt,
                },
                "edges": {},
            }
        )

    def _measure_config(
        self,
        measure: DispersiveMeasurement,
        clock: str,
        with_threshold: bool = True,
    ) -> OperationCompilationConfig:
        threshold = (
            {
                "acq_rotation": measure.acq_rotation,
                "acq_threshold": measure.acq_threshold,
            }
            if with_threshold
            else {}
        )
        return OperationCompilationConfig(
            factory_func=measurement_factories.dispersive_measurement_transmon,
            factory_kwargs={
                "port": self.ports.readout,
                "clock": f"{self.name}.{clock}",
                "pulse_type": measure.pulse_type,
                "pulse_amp": measure.pulse_amp,
                "pulse_duration": measure.pulse_duration,
                "acq_delay": measure.acq_delay,
                "acq_duration": measure.integration_time,
                "acq_label": measure.acq_label,
                "acq_protocol_default": "SSBIntegrationComplex",
                "reset_clock_phase": measure.reset_clock_phase,
                "reference_magnitude": pulse_library.ReferenceMagnitude.from_parameter(
                    measure.reference_magnitude
                ),
                "acq_weights_a": measure.acq_weights_a,
                "acq_weights_b": measure.acq_weights_b,
                "acq_weights_sampling_rate": measure.acq_weights_sampling_rate,
                **threshold,
            },
            gate_info_factory_kwargs=[
                "acq_label_override",
                "coords",
                "bin_mode",
                "acq_protocol",
                "feedback_trigger_label",
            ],
        )
