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

"""Export calibrated parameter values from Redis as a BCC calibration seed.

The seed payload mirrors the legacy ``calibration_seed_template.toml``
shape — a ``calibration_config`` table with ``units`` (static unit
labels), per-element parameter lists, and an LDA discriminator map —
but the static parts are now expressed as :class:`pydantic.BaseModel`
defaults so the package no longer needs to ship a template file.
"""

import json
from enum import Enum
from os import PathLike
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple, Type, Union, Unpack

import tomlkit
from pydantic import BaseModel, ConfigDict, Field

from tergite_tuner.config.session import SessionContext, SessionOptions
from tergite_tuner.utils.logging import logger

# Frequency offset (Hz) used to convert the coupler ``cz_pulse_frequency``
# Redis value to its physical value during the BCC export.
_DOWNCONVERT_FREQUENCY = 4.4e9


class _DataSource(Enum):
    REDIS = "REDIS"
    LITERAL = "LITERAL"


# --------------------------------------------------------------------------
# Pydantic seed model
# --------------------------------------------------------------------------
#
# These models replace the on-disk ``calibration_seed_template.toml``.
# Each ``_*Units`` model holds the static unit labels for a category of
# parameters; ``_CalibrationConfig`` aggregates the units alongside the
# per-element parameter lists; and :class:`CalibrationSeed` is the
# top-level wrapper exported to BCC.


class _QubitUnits(BaseModel):
    frequency: str = "Hz"
    pi_pulse_amplitude: str = ""
    pi_pulse_duration: str = "s"
    pi_pulse_motzoi: str = ""
    pulse_sigma: str = ""
    t1_decoherence: str = "s"
    t2_decoherence: str = "s"
    anharmonicity: str = "Hz"


class _ReadoutResonatorUnits(BaseModel):
    acq_delay: str = "s"
    acq_integration_time: str = "s"
    frequency: str = "Hz"
    pulse_delay: str = "s"
    pulse_duration: str = "s"
    pulse_amplitude: str = ""
    pulse_type: str = ""


class _CouplerUnits(BaseModel):
    frequency: str = "Hz"
    cz_pulse_amplitude: str = ""
    cz_pulse_dc_bias: str = ""
    cz_pulse_duration_constant: str = "s"
    control_rz_lambda: str = "deg"
    target_rz_lambda: str = "deg"
    pulse_type: str = ""


class _Units(BaseModel):
    qubit: _QubitUnits = Field(default_factory=_QubitUnits)
    readout_resonator: _ReadoutResonatorUnits = Field(
        default_factory=_ReadoutResonatorUnits
    )
    coupler: _CouplerUnits = Field(default_factory=_CouplerUnits)


class _CalibrationConfig(BaseModel):
    """Body of a BCC calibration seed."""

    model_config = ConfigDict(extra="allow")

    units: _Units = Field(default_factory=_Units)
    qubit: List[Dict[str, Any]] = Field(default_factory=list)
    readout_resonator: List[Dict[str, Any]] = Field(default_factory=list)
    coupler: List[Dict[str, Any]] = Field(default_factory=list)
    discriminators: Dict[str, Dict[str, Dict[str, Any]]] = Field(
        default_factory=lambda: {"lda": {}}
    )


class CalibrationSeed(BaseModel):
    """Top-level shape of a BCC calibration seed."""

    calibration_config: _CalibrationConfig = Field(default_factory=_CalibrationConfig)


# --------------------------------------------------------------------------
# Redis → seed parameter tables
# --------------------------------------------------------------------------


_qubit_parameters: List[Tuple[str, str, _DataSource, Type]] = [
    ("frequency", "clock_freqs:f01", _DataSource.REDIS, float),
    ("pi_pulse_amplitude", "rxy:amp180", _DataSource.REDIS, float),
    ("pi_pulse_duration", "rxy:duration", _DataSource.REDIS, float),
    ("pi_pulse_motzoi", "rxy:motzoi", _DataSource.REDIS, float),
    ("pulse_type", "Gaussian", _DataSource.LITERAL, str),
    ("pulse_sigma", "rxy:sigma", _DataSource.REDIS, float),
    ("t1_decoherence", "t1_time", _DataSource.REDIS, float),
    ("t2_decoherence", "t2_time", _DataSource.REDIS, float),
]

_readout_resonator_parameters: List[Tuple[str, str, _DataSource, Type]] = [
    ("acq_delay", "measure:acq_delay", _DataSource.REDIS, float),
    ("acq_integration_time", "measure:integration_time", _DataSource.REDIS, float),
    ("frequency", "clock_freqs:readout", _DataSource.REDIS, float),
    ("pulse_delay", "measure:ro_pulse_delay", _DataSource.REDIS, float),
    ("pulse_duration", "measure:pulse_duration", _DataSource.REDIS, float),
    ("pulse_type", "Square", _DataSource.LITERAL, str),
    ("pulse_amplitude", "measure_2state_opt:pulse_amp", _DataSource.REDIS, float),
]

_lda_parameters: List[Tuple[str, str, _DataSource, Type]] = [
    ("coef_0", "lda_coef_0", _DataSource.REDIS, float),
    ("coef_1", "lda_coef_1", _DataSource.REDIS, float),
    ("intercept", "lda_intercept", _DataSource.REDIS, float),
]

_coupler_parameters: List[Tuple[str, str, _DataSource, Type]] = [
    ("frequency", "cz_pulse_frequency", _DataSource.REDIS, float),
    ("cz_pulse_amplitude", "cz_pulse_amplitude", _DataSource.REDIS, float),
    ("cz_pulse_dc_bias", "parking_current", _DataSource.REDIS, float),
    ("cz_pulse_duration_constant", "cz_pulse_duration", _DataSource.REDIS, float),
    ("control_rz_lambda", "cz_dynamic_control", _DataSource.REDIS, float),
    ("target_rz_lambda", "cz_dynamic_target", _DataSource.REDIS, float),
    ("pulse_type", "wacqt_cz", _DataSource.LITERAL, str),
]


def extract_bcc_params(
    env_file: Optional[Union[str, "PathLike[str]"]] = None,
    format: Literal["dict", "json", "toml"] = "dict",
    output: Optional[Union[str, "PathLike[str]"]] = None,
    **session_options: Unpack[SessionOptions],
) -> Any:
    """Build a BCC calibration seed payload from redis-stored values.

    Args:
        env_file: optional path to a ``.env`` file used to populate the
            internal :class:`SessionContext`.
        format: ``'dict'`` returns a Python dict, ``'json'`` returns a
            JSON string, ``'toml'`` returns a TOML string. The result is
            also written to ``output`` when supplied (in the same form,
            with the dict variant written as TOML on disk).
        output: optional path to write the seed to. The file extension
            is ignored — the format follows the ``format`` argument.
        **session_options: any :class:`SessionContext` field — most
            usefully ``qubits``, ``couplers``, and ``redis_url`` — to
            override values that would otherwise come from
            ``env_file`` / ``os.environ``.
            See `<tergite_tuner.config.session.SessionContext>`_ for details.

    Returns:
        The payload in the requested format.
    """
    session = SessionContext.from_env(env_file, **session_options)
    redis_connection = session.redis
    qubits = session.qubits
    couplers = session.couplers or []

    qubit_entries = [
        _assemble_parameters(_qubit_parameters, q, redis_connection) for q in qubits
    ]
    readout_resonator_entries = [
        _assemble_parameters(_readout_resonator_parameters, q, redis_connection)
        for q in qubits
    ]
    lda_entries = {
        q: _assemble_parameters(_lda_parameters, q, redis_connection, set_id=False)
        for q in qubits
    }
    coupler_entries = [
        _assemble_parameters(
            _coupler_parameters, c, redis_connection, redis_prefix="couplers"
        )
        for c in couplers
    ]

    seed = CalibrationSeed(
        calibration_config=_CalibrationConfig(
            qubit=qubit_entries,
            readout_resonator=readout_resonator_entries,
            coupler=coupler_entries,
            discriminators={"lda": lda_entries},
        )
    )

    payload = seed.model_dump()

    if format == "dict":
        result: Any = payload
    elif format == "json":
        result = json.dumps(payload, indent=2)
    elif format == "toml":
        result = tomlkit.dumps(payload)
    else:
        raise ValueError(
            f"Invalid format: {format!r}. Must be 'dict', 'json', or 'toml'."
        )

    if output is not None:
        output_path = Path(output)
        if format == "dict":
            # On-disk artefact stays in the historical TOML form while
            # the in-memory ``dict`` is returned to the caller.
            with open(output_path, "w") as f_:
                f_.write(tomlkit.dumps(payload))
        else:
            with open(output_path, "w") as f_:
                f_.write(result)

    return result


def _assemble_parameters(
    parameter_map: List[Tuple[str, str, _DataSource, Type]],
    object_id: str,
    redis_connection,
    set_id: bool = True,
    redis_prefix: str = "transmons",
) -> Dict[str, Any]:
    if not set_id:
        parameterized_return_object: Dict[str, Any] = {}
    else:
        parameterized_return_object = {"id": object_id}

    for parameter_ in parameter_map:
        if parameter_[2] == _DataSource.REDIS:
            redis_value_ = redis_connection.hget(
                f"{redis_prefix}:{object_id}", parameter_[1]
            )
            parameterized_return_object[parameter_[0]] = parameter_[3](
                redis_value_ if redis_value_ is not None else 0
            )
        if parameter_[2] == _DataSource.LITERAL:
            parameterized_return_object[parameter_[0]] = parameter_[3](parameter_[1])

        # Special case: down-converter correction for the coupler frequency.
        if parameter_[1] == "cz_pulse_frequency":
            logger.info(
                f"Adjusting coupler frequency about {_DOWNCONVERT_FREQUENCY}GHz "
                f"for {object_id}."
            )
            parameterized_return_object[parameter_[0]] = (
                _DOWNCONVERT_FREQUENCY - parameterized_return_object[parameter_[0]]
            )

    return parameterized_return_object
