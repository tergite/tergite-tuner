# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs AB 2025, 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Export calibrated parameter values from Redis as a BCC calibration seed."""

import ast
import json
import re
from os import PathLike
from typing import (
    Annotated,
    Any,
    Dict,
    List,
    Literal,
    Optional,
    Tuple,
    TypeVar,
    Union,
    Unpack,
)

import numpy as np
import tomlkit
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator

from tergite_tuner.config.session import SessionContext, SessionOptions
from tergite_tuner.storage.redis import QueryOptions

_CalibValueType = TypeVar("_CalibValueType", int, float, str)
_NodeState = Literal["calibrated", "not_calibrated"]
_DOWNCONVERT_FREQUENCY = 4.4e9
_NUMPY_FLOAT_PATTERN = re.compile(r"np\.float\d*")


def read_result(
    session: SessionContext, session_only: bool = True
) -> "CalibrationResults":
    """Retrieves the results after tuneup

    Args:
        session: the session context to use
        session_only: if True, retrieves results created by current session.
            Else, all available results will be returned. Default is True.

    Returns:
        the results in redis for the current session
    """
    pks = session.qubits + session.couplers
    affected_fields = session.redis_fields_touched.keys()
    query_func = None

    if session_only:

        def query_func(opts: QueryOptions):
            return any(opts["field"] in k for k in affected_fields)

    data = session.redis_store.find_many(pks=pks, query=query_func)
    return CalibrationResults.model_validate(data)


def generate_calib_seed_file(
    path: Union[str, "PathLike[str]"] = "calibration.seed.toml",
    session: Optional[SessionContext] = None,
    env_file: Optional[Union[str, "PathLike[str]"]] = None,
    coupler_name_map: Optional[Dict[str, str]] = None,
    **session_options: Unpack[SessionOptions],
):
    """Build a calibration seed payload from redis-stored values.

    Args:
        path: path to write the seed to. The file extension
            is ignored — the format follows the ``format`` argument.
        session: session context to use for session.
        env_file: optional path to a ``.env`` file used to populate the
            internal :class:`SessionContext`.
        coupler_name_map: dict of coupler_name (in redis) -> coupler name (in bcc) mapping
        **session_options: any :class:`SessionContext` field — most
            usefully ``qubits``, ``couplers``, and ``redis_url`` — to
            override values that would otherwise come from
            ``env_file`` / ``os.environ``.
            See `<tergite_tuner.config.session.SessionContext>`_ for details.

    Returns:
        The payload in the requested format.
    """
    if session is None:
        session = SessionContext.from_env(env_file, **session_options)

    if coupler_name_map is None:
        coupler_name_map = {k: k for k in session.couplers}

    results = read_result(session, session_only=False)
    transmon_data = results.transmons
    coupler_data = results.couplers

    config_file_data = {
        "calibration_config": {
            "units": {
                "qubit": dict(
                    frequency="Hz",
                    t1_decoherence="us",
                    t2_decoherence="us",
                    anharmonicity="Hz",
                    pi_pulse_amplitude="",
                    pi_pulse_duration="s",
                    pi_pulse_motzoi="",
                    pulse_sigma="",
                ),
                "readout_resonator": dict(
                    acq_delay="s",
                    acq_integration_time="s",
                    frequency="Hz",
                    pulse_delay="s",
                    pulse_duration="s",
                    pulse_amplitude="",
                    pulse_type="",
                ),
                "coupler": dict(
                    frequency="Hz",
                    cz_pulse_amplitude="",
                    cz_pulse_dc_bias="",
                    cz_pulse_duration_constant="s",
                    control_rz_lambda="rad",
                    target_rz_lambda="rad",
                    pulse_type="",
                ),
            },
            "qubit": [
                dict(
                    id=q,
                    frequency=item.clock_freqs.f01,
                    pi_pulse_amplitude=item.rxy.amp180,
                    pi_pulse_duration=item.rxy.duration,
                    pi_pulse_motzoi=item.rxy.motzoi,
                    pulse_type="Gaussian",
                    pulse_sigma=item.rxy.sigma or 0,  # not necessary
                    t1_decoherence=item.t1_time,
                    t2_decoherence=item.t2_echo_time,
                )
                for q, item in transmon_data.items()
            ],
            "coupler": [
                dict(
                    id=coupler_name_map[c],
                    frequency=_DOWNCONVERT_FREQUENCY - item.cz_pulse_frequency,
                    cz_pulse_amplitude=item.cz_pulse_amplitude,
                    cz_pulse_dc_bias=item.parking_current or 0,  # not necessary
                    cz_pulse_duration_constant=item.cz_pulse_duration,
                    control_rz_lambda=np.deg2rad(item.cz_dynamic_control),
                    target_rz_lambda=np.deg2rad(item.cz_dynamic_target),
                    pulse_type="wacqt_cz",
                )
                for c, item in coupler_data.items()
            ],
            "readout_resonator": [
                dict(
                    id=q,
                    acq_delay=item.measure.acq_delay,
                    acq_integration_time=item.measure.integration_time,
                    frequency=item.extended_clock_freqs.readout_2state_opt,
                    pulse_delay=item.measure.ro_pulse_delay or 0,  # not necessary
                    pulse_duration=item.measure.pulse_duration,
                    pulse_type="Square",
                    pulse_amplitude=item.measure_2state_opt.pulse_amp,
                )
                for q, item in transmon_data.items()
            ],
            "discriminators": {
                "lda": {
                    q: dict(
                        coef_0=item.lda_coef_0,
                        coef_1=item.lda_coef_1,
                        intercept=item.lda_intercept,
                    )
                    for q, item in transmon_data.items()
                }
            },
        }
    }

    with open(path, "w") as file:
        tomlkit.dump(config_file_data, file)


def _validate_numpy_tuple(v: Any) -> Any:
    """Validates a field of tuples of numpy float64"""
    if isinstance(v, str):
        try:
            v = ast.literal_eval(_NUMPY_FLOAT_PATTERN.sub("", v))
        except (ValueError, SyntaxError) as e:
            raise ValueError(f"Could not parse numpy tuple string: {e}")

    if isinstance(v, (list, tuple)):
        return tuple(np.float64(item) for item in v)
    return v


# The Annotated Field
NumpyFloatTuple = Annotated[
    Tuple[np.float64, np.float64], BeforeValidator(_validate_numpy_tuple)
]


class _RedisDict(BaseModel):
    """A representation of dictionaries in redis"""

    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)

    @model_validator(mode="before")
    @classmethod
    def convert_nans(cls, data: Any) -> Any:
        """Coverts all 'nan' values to Not set."""
        if isinstance(data, dict):
            return {k: v for k, v in data.items() if v != "nan"}
        return data


class CalibrationResults(_RedisDict):
    """The combined data structure of Bcc params as saved in redis"""

    transmons: Dict[str, "_QubitInRedis"] = {}
    couplers: Dict[str, "_CouplerInRedis"] = {}
    cs: Dict[str, "_CsInRedis"] = {}


class _QubitInRedis(_RedisDict):
    """The data structure of qubits as saved in redis"""

    clock_freqs: Optional["_QubitClockFreqsInRedis"] = None
    rxy: Optional["_QubitRxyInRedis"] = None
    t1_time: float | None = None
    t1_time_error: float | None = None
    t2_echo_time: float | None = None
    t2_echo_time_error: float | None = None
    t2_time: float | None = None
    t2_time_error: float | None = None
    lda_coef_0: float | None = None
    lda_coef_1: float | None = None
    lda_intercept: float | None = None
    measure: Optional["_QubitMeasureInRedis"] = None
    measure_1: Optional["_QubitMeasureInRedis"] = None
    measure_2: Optional["_QubitMeasureInRedis"] = None
    measure1: Optional["_QubitMeasureInRedis"] = None
    measure2: Optional["_QubitMeasureInRedis"] = None
    extended_clock_freqs: Optional["_QubitExtendedClockFreqsInRedis"] = None
    measure_2state_opt: Optional["_QubitMeasureInRedis"] = None
    measure_3state_opt: Optional["_QubitMeasureInRedis"] = None
    omega_20: float | None = None
    omega_20_error: float | None = None
    center_0: NumpyFloatTuple | None = Field(None, alias="center|0>")
    center_1: NumpyFloatTuple | None = Field(None, alias="center|1>")
    center_2: NumpyFloatTuple | None = Field(None, alias="center|2>")
    lda_coef_1_error: float | None = None
    lda_coef_0_error: float | None = None
    centroid_I: float | None = None
    centroid_Q: float | None = None
    centroid_Q_error: float | None = None
    spec: Optional["_QubitSpecInRedis"] = None
    resonator_minimum: float | None = None
    resonator_minimum_error: float | None = None
    resonator_minimum_1: float | None = None
    resonator_minimum_1_error: float | None = None
    r12: Optional["_QubitR12InRedis"] = None
    inv_cm_opt_error: float | None = None
    fidelity_error: float | None = None
    lda_intercept_error: float | None = None
    omega_01: float | None = None
    omega_01_error: float | None = None
    omega_12: float | None = None
    omega_12_error: float | None = None
    purity_fidelity: float | None = None
    inv_cm_opt: float | None = None
    centroid_I_error: float | None = None
    attenuation: float | None = None
    leakage: float | None = None
    leakage_error: float | None = None
    Ql: float | None = None
    Ql_error: float | None = None
    Ql_1: float | None = None
    Ql_1_error: float | None = None
    VNA_f01_frequency: float | None = None
    VNA_f12_frequency: float | None = None
    fidelity: float | None = None
    reset: Optional["_ResetInRedis"] = None
    readout_matrix: Optional[List[List[float]]] | None = None


class _CouplerInRedis(_RedisDict):
    """The data structure of coupler as saved in redis"""

    cz_pulse_frequency: float | None = None
    cz_pulse_amplitude: float | None = None
    parking_current: float | None = None
    cz_pulse_duration: float | None = None
    cz_dynamic_control: float | None = None
    cz_dynamic_target: float | None = None
    target_local_phase: float | None = None
    qubit_crossing_points: List[float] | None = None
    cz_pulse_frequency_error: float | None = None
    cz_fidelity: float | None = None
    cz_dynamic_amplitude: float | None = None
    cz_working_durations_in_ns: List[float] | None = None
    cz_dynamic_control_error: float | None = None
    control_local_phase: float | None = None
    cz_working_frequencies_error: float | None = None
    spec: Optional["_CouplerSpecInRedis"] = None
    cz_working_frequencies: List[float] | None = None
    cz_pulse_duration_error: float | None = None
    cz_working_durations_in_ns_error: float | None = None
    reset: Optional["_ResetInRedis"] = None
    tqg_fidelity: float | None = None
    cz_dynamic_target_error: float | None = None
    attenuation: float | None = None


class _CsInRedis(_RedisDict):
    """The data structure of CS (calibration supervisor) as saved in redis"""

    resonator_spectroscopy: _NodeState | None = None
    qubit_01_spectroscopy: _NodeState | None = None
    rabi_oscillations: _NodeState | None = None
    ramsey_correction: _NodeState | None = None
    motzoi_parameter: _NodeState | None = None
    n_rabi_oscillations: _NodeState | None = None
    resonator_spectroscopy_1: _NodeState | None = None
    qubit_12_spectroscopy: _NodeState | None = None
    rabi_oscillations_12: _NodeState | None = None
    ramsey_correction_12: _NodeState | None = None
    resonator_spectroscopy_2: _NodeState | None = None
    ro_frequency_three_state_optimization: _NodeState | None = None
    ro_amplitude_three_state_optimization: _NodeState | None = None
    qubit_bring_up_spectroscopy: _NodeState | None = None
    t1: _NodeState | None = None
    t2: _NodeState | None = None
    t2_echo: _NodeState | None = None
    ro_frequency_two_state_optimization: _NodeState | None = None
    ro_amplitude_two_state_optimization: _NodeState | None = None
    randomized_benchmarking: _NodeState | None = None
    purity_benchmarking: _NodeState | None = None
    punchout: _NodeState | None = None


class _QubitClockFreqsInRedis(_RedisDict):
    """The data structure of qubit:clock_freqs as saved in redis"""

    f01: float | None = None
    f01_error: float | None = None
    readout_error: float | None = None
    readout: float | None = None
    f12: float | None = None
    f12_error: float | None = None


class _QubitRxyInRedis(_RedisDict):
    """The data structure of qubit:rxy as saved in redis"""

    amp180: float | None = None
    amp180_error: float | None = None
    duration: float | None = None
    motzoi: float | None = None
    motzoi_error: float | None = None
    sigma: float = 0


class _QubitMeasureInRedis(_RedisDict):
    """The data structure of qubit:measure*  as saved in redis"""

    acq_delay: float | None = None
    integration_time: float | None = None
    ro_pulse_delay: float = 0
    pulse_duration: float | None = None
    pulse_amp: float | None = None
    pulse_amp_error: float | None = None
    acq_threshold: float | None = None
    acq_threshold_error: float | None = None
    acq_rotation: float | None = None
    acq_rotation_error: float | None = None


class _QubitExtendedClockFreqsInRedis(_RedisDict):
    """The data structure of qubit:extended_clock_freqs as saved in redis"""

    readout_2state_opt: float | None = None
    readout_3state_opt: float | None = None
    readout_2_error: float | None = None
    readout_1_error: float | None = None
    readout_1: float | None = None
    readout_3state_opt_error: float | None = None
    readout_2: float | None = None
    readout_2state_opt_error: float | None = None


class _QubitSpecInRedis(_RedisDict):
    """The data structure of qubit:spec as saved in redis"""

    spec_ampl_12_optimal: float | None = None
    spec_ampl_optimal: float | None = None
    spec_ampl_optimal_error: float | None = None
    spec_amp: float | None = None
    spec_ampl_12_optimal_error: float | None = None
    spec_duration: float | None = None


class _QubitR12InRedis(_RedisDict):
    """The data structure of qubit:r12 as saved in redis"""

    ef_amp180_error: float | None = None
    ef_motzoi: float | None = None
    ef_amp180: float | None = None
    ef_motzoi_error: float | None = None


class _CouplerSpecInRedis(_RedisDict):
    """The data structure of coupler:spec as saved in redis"""

    spec_amp: float | None = None
    spec_duration: float | None = None


class _ResetInRedis(_RedisDict):
    """The data structure of coupler:reset as saved in redis"""

    duration: float | None = None
