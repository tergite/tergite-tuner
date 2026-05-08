# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2023, 2024, 2025
# (C) Copyright Liangyu Chen 2023, 2024
# (C) Copyright Stefan Hill 2024
# (C) Copyright Michele Faucci Giannelli 2024, 2025
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

from abc import ABC, abstractmethod
from collections.abc import Iterable
from os import PathLike
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Literal, Optional, Tuple, Type

import matplotlib
import numpy as np
import xarray

from tergite_tuner.lib.base.analysis import BaseNodeAnalysis
from tergite_tuner.lib.base.measurement import BaseMeasurement, MeasurementType
from tergite_tuner.lib.utils.device import (
    close_device_resources,
    configure_device,
    save_serial_device,
)
from tergite_tuner.lib.utils.schedule_execution import execute_schedule, get_compiler
from tergite_tuner.utils.dto.enums import MeasurementMode
from tergite_tuner.utils.dto.qoi import QOI
from tergite_tuner.utils.hardware.spi import SpiDAC
from tergite_tuner.utils.io.dataset import save_dataset
from tergite_tuner.utils.logging import logger
from tergite_tuner.utils.logging.visuals import print_measurement_info
from tergite_tuner.utils.measurement_utils import samplespace_dimensions
from tergite_tuner.utils.misc.helpers import insert_nested_key, to_flat_map

if TYPE_CHECKING:
    from quantify_scheduler.device_under_test.quantum_device import QuantumDevice
    from quantify_scheduler.instrument_coordinator.instrument_coordinator import (
        CompiledSchedule,
        InstrumentCoordinator,
    )

    from tergite_tuner.config.session import SessionContext


class BaseNode(ABC):
    name: str
    measurement_cls: Type["BaseMeasurement"]
    analysis_cls: Type["BaseNodeAnalysis"]
    measurement_type_cls: Type["MeasurementType"]

    def __init__(self, session: "SessionContext", **node_dictionary):
        self.session = session
        # The matplotlib backend depends on whether plots should be shown
        # while the run is in progress. Set this once per node to keep the
        # behaviour consistent across the run.
        matplotlib.use("tkagg" if session.save_plot else "agg")
        self.node_dictionary = node_dictionary
        self.lab_instr_coordinator: Optional["InstrumentCoordinator"] = None
        self.spi_manager: Optional[SpiDAC] = None
        self.schedule_samplespace = {}
        self.external_samplespace = {}
        self.redis_fields = []
        self.all_qubits = []

        # These may be modified while the node runs
        self.outer_schedule_samplespace = {}
        self.reduced_external_samplespace = {}
        self.loops = None
        self.schedule_keywords = {}
        self.analysis_keywords = {}

        self.samplespace = self.schedule_samplespace | self.external_samplespace

        self.device: Optional["QuantumDevice"] = None

    @abstractmethod
    def precompile(self, samplespace):
        pass

    @classmethod
    @abstractmethod
    def persist_qois(cls, session: "SessionContext", node_name: str):
        """Saves the qois of this node in the store

        Args:
            session: The session context we are working in
            node_name: The name of the node
        """
        raise NotImplementedError(f"Persist qois is not implemented for {cls.__name__}")

    def measure_node(self, cluster_status) -> xarray.Dataset:
        """
        Here we attach the measure_node method according to the
        measurement_type_cls: ScheduleNode or ExternalParameterNode or something else
        """
        measurement_type = self.measurement_type_cls(self)
        dataset = measurement_type.measure_node(cluster_status)
        return dataset

    def calibrate(self, data_path, measurement_mode, save_plot):
        if measurement_mode != MeasurementMode.re_analyse:
            result_dataset = self.measure_node(measurement_mode)
            save_serial_device(self.device, data_path)
            save_dataset(result_dataset, self.name, data_path)
        # After the measurement free the device resources
        close_device_resources(self.device)
        self.post_process(data_path, save_plot)
        logger.info("analysis completed")

    def measure_compiled_schedule(
        self,
        compiled_schedule: "CompiledSchedule",
        measurement_mode=MeasurementMode.real,
        measurement: Tuple[int, int] = (1, 1),
    ) -> xarray.Dataset:
        """
        Execute a measurement for a node and save the resulting dataset.

        Args:
            compiled_schedule (CompiledSchedule): The compiled schedule to execute.
            measurement_mode (MeasurementMode.real): The status of the measurement mode.
            measurement (tuple): Tuple of (current_measurement, total_measurements).

        Returns:
            xarray.Dataset: The dataset containing the measurement results.
        """

        schedule_duration = self._calculate_schedule_duration(compiled_schedule)
        print_measurement_info(schedule_duration, measurement)

        raw_dataset = execute_schedule(
            compiled_schedule,
            schedule_duration,
            self.lab_instr_coordinator,
            measurement_mode,
        )

        if measurement_mode == MeasurementMode.dummy:
            raw_dataset = self.generate_dummy_dataset()
        result_dataset = self.configure_dataset(raw_dataset)

        logger.info("Finished measurement")
        return result_dataset

    def _calculate_schedule_duration(
        self, compiled_schedule: "CompiledSchedule"
    ) -> float:
        """Calculate the total duration of the schedule."""
        duration = compiled_schedule.get_schedule_duration()
        if "loop_repetitions" in self.node_dictionary:
            duration *= self.node_dictionary["loop_repetitions"]
        return duration

    def post_process(self, data_path: PathLike[str], save_plot: bool = False):
        analysis_kwargs = getattr(self, "analysis_keywords", dict())
        node_analysis: BaseNodeAnalysis = self.analysis_cls(
            name=self.name,
            redis_fields=self.redis_fields,
            session=self.session,
            **analysis_kwargs,
        )
        results = node_analysis.analyze_node(data_path, save_plot)
        redis_data = {}

        for pk, qoi in results.items():
            if not qoi.analysis_successful:
                logger.warning(f"Analysis failed for {pk}")
                continue

            try:
                record = qoi_to_redis_record(qoi, redis_fields=self.redis_fields)
            except ValueError as e:
                raise ValueError(f"Element: {pk}: {e}") from e

            collection = "couplers" if "_" in pk else "transmons"
            insert_nested_key(redis_data, path=(collection, pk), value=record)
            insert_nested_key(redis_data, path=("cs", pk), value="calibrated")

        self.session.redis_store.save_many(redis_data)
        self.session.update_redis_fields_log(self)
        return results

    def configure_dataset(
        self,
        raw_ds: xarray.Dataset,
    ) -> xarray.Dataset:
        """
        The dataset retrieved from the instrument coordinator is
        too bare-bones. Here the dims, coords and data_vars are configured
        """
        dataset = xarray.Dataset(attrs={"elements": []})

        raw_ds_keys = raw_ds.data_vars.keys()
        measurement_qubits = self.all_qubits
        samplespace = self.schedule_samplespace

        sweep_quantities = samplespace.keys()

        n_qubits = len(measurement_qubits)

        for key in raw_ds_keys:
            key_indx = key % n_qubits  # this is to handle ro_opt_frequencies node where
            coords_dict = {}
            measured_qubit = measurement_qubits[key_indx]
            dimensions = samplespace_dimensions(samplespace, self.loops)

            for quantity in sweep_quantities:
                # eg settable_elements -> ['q1','q2',...] or ['q1_q2','q3_q4',...] :
                settable_elements = samplespace[quantity].keys()

                # distinguish if the settable is on a qubit or a coupler:
                if measured_qubit in settable_elements:
                    element = measured_qubit
                    element_type = "qubit"
                else:
                    matching = [s for s in settable_elements if measured_qubit in s]
                    # TODO: len(matching) == 1 implies that we operate on only 1 coupler.
                    # To be changed in future
                    if len(matching) == 1 and "_" in matching[0]:
                        element = matching[0]
                        element_type = "coupler"
                    else:
                        raise ValueError()

                coord_key = quantity + element

                settable_values = samplespace[quantity][element]
                coord_attrs = {
                    "element_type": element_type,  # 'element_type' is ether 'qubit' or 'coupler'
                    element_type: element,
                    "measured_qubit": measured_qubit,
                    "long_name": f"{coord_key}",
                    "units": "NA",
                }

                # This is for measurements of type OuterScheduleNode:
                if not isinstance(settable_values, Iterable):
                    settable_values = np.array([settable_values])

                coords_dict[coord_key] = (coord_key, settable_values, coord_attrs)

            if self.loops is not None:
                coords_dict["loops"] = (
                    "loops",
                    np.arange(self.loops),
                    {"element_type": "NA"},
                )

            partial_ds = xarray.Dataset(coords=coords_dict)

            data_values = raw_ds[key].values

            data_values = data_values.reshape(*dimensions, order="F")

            # the element under examination ...
            # ... in single qubit nodes the element is just the measured_qubit
            element = measured_qubit
            # ... but in coupler nodes the element is the coupler attached to the
            # measured_qubit whose resonator populates the raw data-array
            if issubclass(self.__class__, CouplerNode):
                for coupler in self.couplers:
                    if measured_qubit in coupler:
                        element = coupler
                        break

            attributes = {
                "qubit": measured_qubit,
                "element": element,
                "long_name": f"y{measured_qubit}",
                "units": "NA",
            }
            partial_ds[f"y{measured_qubit}"] = (
                tuple(coords_dict.keys()),
                data_values,
                attributes,
            )

            dataset = xarray.merge([dataset, partial_ds])
            dataset.attrs["elements"].append(element)
        # take the set of elements because couplers appear duplicated
        dataset.attrs["elements"] = list(set(dataset.attrs["elements"]))
        return dataset


class QubitNode(BaseNode):
    name: str
    qubit_qois: list[str] | None = None

    def __init__(
        self,
        all_qubits: list[str],
        couplers: list[str],
        session: "SessionContext",
        **node_keywords,
    ):
        super().__init__(session, **node_keywords)
        self.all_qubits = all_qubits
        self.couplers = couplers
        self.qubit_state = 0  # can be 0 or 1 or 2

        if self.qubit_qois is not None:
            self.redis_fields = self.qubit_qois

        self.device = configure_device(
            self.name,
            qubits=self.all_qubits,
            couplers=self.couplers,
            session=self.session,
        )

    def precompile(self, schedule_samplespace: dict) -> "CompiledSchedule":
        import quantify_scheduler.backends.qblox.constants as constants

        constants.GRID_TIME_TOLERANCE_TIME = 5e-2

        transmons_dict = {
            qubit: self.device.get_element(qubit) for qubit in self.all_qubits
        }
        measurement_class = self.measurement_cls(transmons_dict)
        schedule = measurement_class.schedule_function(
            **schedule_samplespace, **self.schedule_keywords
        )

        compiler = get_compiler(prefix=self.name)

        compilation_config = self.device.generate_compilation_config()
        logger.info("Starting Compiling")
        compiled_schedule = compiler.compile(
            schedule=schedule, config=compilation_config
        )

        return compiled_schedule

    @classmethod
    def persist_qois(cls, session: "SessionContext", node_name: str):
        """Saves the qois of this node in the store

        Args:
            session: The session context we are working in
            node_name: The name of the node
        """
        redis_store = session.redis_store
        qubits = session.qubits

        qubit_qois = cls.qubit_qois
        if qubit_qois is None:
            logger.warning(f"No qois for node {node_name}")
            return

        zero_based_qois = (
            "measure_3state_opt:pulse_amp",
            "measure_2state_opt:pulse_amp",
            "rxy:motzoi",
            "r12:ef_motzoi",
        )
        new_qubit_data = {k: (0 if k in zero_based_qois else "nan") for k in qubit_qois}

        query_result = redis_store.find_many("transmons", pks=qubits)
        existing_qubits = query_result.get("transmons", {})

        query_result = redis_store.find_many("cs", pks=qubits)
        existing_supervisor_records = query_result.get("cs", {})

        existing_qubits = {k: dict(to_flat_map(v)) for k, v in existing_qubits.items()}

        updated_qubit_data = {
            q: {
                k: v
                for k, v in new_qubit_data.items()
                if k not in existing_qubits.get(q, {})
            }
            for q in qubits
        }
        updated_supervisor_data = {
            q: {node_name: "not_calibrated"}
            for q in qubits
            if node_name not in existing_supervisor_records.get(q, {})
        }

        redis_store.save_many(
            {
                "transmons": updated_qubit_data,
                "cs": updated_supervisor_data,
            }
        )

    def __str__(self):
        return f"Node representation for {self.name} on qubits {self.all_qubits}"

    def __format__(self, message):
        return f"Node representation for {self.name} on qubits {self.all_qubits}"

    def __repr__(self):
        return f"Node({self.name}, {self.all_qubits})"


class CouplerNode(BaseNode):
    name: str
    coupler_qois: list[str]

    def __init__(self, couplers: list[str], session: "SessionContext", **node_keywords):
        super().__init__(session, **node_keywords)
        self.couplers = couplers
        self.edges = couplers
        self.all_qubits = sorted(set(self.get_coupled_qubits()))

        if self.coupler_qois is not None:
            self.redis_fields = self.coupler_qois

        self.device = configure_device(
            self.name,
            qubits=self.all_qubits,
            couplers=self.couplers,
            session=self.session,
        )

    def measure_node(self, cluster_status) -> xarray.Dataset:
        """
        Here we attach the measure_node method according to the
        measurement_type_cls: ScheduleNode or ExternalParameterNode or something else

        Overwrite the base method, to set the updated SPI currents before the measurement.
        """
        self.set_parking_current_from_redis()
        measurement_type = self.measurement_type_cls(self)
        dataset = measurement_type.measure_node(cluster_status)
        return dataset

    @classmethod
    def persist_qois(cls, session: "SessionContext", node_name: str):
        """Saves the qois of this node in the store

        Args:
            session: The session context we are working in
            node_name: The name of the node
        """
        redis_store = session.redis_store
        couplers = session.couplers

        coupler_qois = cls.coupler_qois
        if coupler_qois is None:
            return

        new_coupler_data = dict.fromkeys(coupler_qois, "nan")
        query_result = redis_store.find_many("couplers", pks=couplers)
        existing_couplers = query_result.get("couplers", {})

        query_result = redis_store.find_many("cs", pks=couplers)
        existing_supervisor_records = query_result.get("cs", {})

        existing_couplers = {
            k: dict(to_flat_map(v)) for k, v in existing_couplers.items()
        }

        updated_coupler_data = {
            c: {
                k: v
                for k, v in new_coupler_data.items()
                if k not in existing_couplers.get(c, {})
            }
            for c in couplers
        }

        updated_supervisor_data = {
            c: {node_name: "not_calibrated"}
            for c in couplers
            if node_name not in existing_supervisor_records.get(c, {})
        }

        redis_store.save_many(
            {
                "couplers": updated_coupler_data,
                "cs": updated_supervisor_data,
            }
        )

    def set_parking_current_from_redis(self):
        """
        At the beginning of the calibration, the parking current is set by
        the calibration supervisor from the device_config value. This value
        can be updated by the cz_parametrization measurement which updates the
        parking current value on redis.

        This method fetches the redis value and sets the update DC current
        to the appropriate SPI dacs.
        """
        redis_data = self.session.redis_store.find_many(
            collection="couplers", pks=self.couplers
        )
        try:
            currents_dict = {
                k: v["parking_current"] for k, v in redis_data["couplers"].items()
            }
        except KeyError:
            logger.error(f"Some couplers are missing currents: {redis_data}")
            return

        # do not set dac currents when in calibration
        if not self.session.is_recalibration:
            logger.status("Setting updated DC currents")
            self.spi_manager.set_dac_current(currents_dict)
        else:
            logger.debug("Skipping setting DC currents")

    def get_coupled_qubits(self) -> list:
        coupled_qubits = []
        for coupler in self.couplers:
            qubits = coupler.split(sep="_")
            coupled_qubits.append(qubits[0])
            coupled_qubits.append(qubits[1])
        return coupled_qubits

    def gate_qubit_types_dict(self) -> dict[str, dict]:
        redis_data = self.session.redis_store.find_many(
            collection="couplers", pks=self.couplers
        )
        try:
            return {
                k: {
                    "control_qubit": v["control_qubit"],
                    "target_qubit": v["target_qubit"],
                }
                for k, v in redis_data["couplers"].items()
            }
        except KeyError as e:
            logger.warning(f"Some couplers control and target qubits are missing: {redis_data}")
            raise e

    def validate(self) -> None:
        all_coupled_qubits = []
        for coupler in self.couplers:
            all_coupled_qubits += coupler.split("_")
        if len(all_coupled_qubits) > len(set(all_coupled_qubits)):
            logger.info("Couplers share qubits")
            raise ValueError("Improper Couplers")

    def transition_frequency(
        self, coupler: str, phase_path: Literal["via_20", "via_02"]
    ) -> float:
        redis_store = self.session.redis_store
        qubit_roles = self.gate_qubit_types_dict()[coupler]
        c_qubit = qubit_roles["control_qubit"]
        t_qubit = qubit_roles["target_qubit"]
        c_record = redis_store.find_one("transmons", c_qubit)
        t_record = redis_store.find_one("transmons", t_qubit)
        c_f01 = float(c_record["clock_freqs"]["f01"])
        t_f01 = float(t_record["clock_freqs"]["f01"])
        c_f12 = float(c_record["clock_freqs"]["f12"])
        t_f12 = float(t_record["clock_freqs"]["f12"])

        if phase_path == "via_20":
            ac_frequency = np.abs(c_f01 + t_f01 - (c_f01 + c_f12))
        elif phase_path == "via_02":
            ac_frequency = np.abs(c_f01 + t_f01 - (t_f01 + t_f12))
        else:
            raise ValueError("Invalid Phase path")

        ac_frequency = int(ac_frequency / 1e4) * 1e4
        logger.info(f"{ ac_frequency/1e6 = } MHz for coupler: {coupler}")

        return ac_frequency

    def precompile(self, schedule_samplespace: dict) -> "CompiledSchedule":
        import quantify_scheduler.backends.qblox.constants as constants

        constants.GRID_TIME_TOLERANCE_TIME = 5e-2

        transmons_dict = {
            qubit: self.device.get_element(qubit) for qubit in self.all_qubits
        }
        edges_dict = {
            coupler: self.device.get_edge(coupler) for coupler in self.couplers
        }
        measurement_class = self.measurement_cls(transmons_dict, edges_dict)
        schedule = measurement_class.schedule_function(
            **schedule_samplespace, **self.schedule_keywords
        )

        compiler = get_compiler(prefix=self.name)

        compilation_config = self.device.generate_compilation_config()
        logger.info("Starting Compiling")
        compiled_schedule = compiler.compile(
            schedule=schedule, config=compilation_config
        )

        return compiled_schedule

    def __str__(self):
        return f"Node representation for {self.name} on couplers {self.couplers}"

    def __format__(self, message):
        return f"Node representation for {self.name} on couplers {self.couplers}"

    def __repr__(self):
        return f"Node({self.name}, {self.couplers})"


def qoi_to_redis_record(
    qoi: QOI = None,
    redis_fields: List[str] = (),
) -> Dict[str, Any]:
    """Converts the quantity of interest (QOI) into a redis record

    Args:
        qoi: The quantity of interest as QOI wrapped object
        redis_fields: List of redis fields that are allowed for this QOI

    Returns:
        the record that would be saved in redis for this QOI
    """
    results = qoi.analysis_result
    rogue_fields = results.keys() - set(redis_fields)
    if rogue_fields:
        raise ValueError(
            f"The QOI's {rogue_fields} are not in redis fields: {redis_fields}"
        )

    record = {}
    for k, res in results.items():
        record[k] = res["value"]
        record[f"{k}_error"] = res["error"]

    return record
