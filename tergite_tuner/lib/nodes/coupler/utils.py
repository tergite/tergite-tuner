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
"""What the coupler nodes read about a coupler from the store, and their shared dummy shots."""

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Literal

import numpy as np

from tergite_tuner.utils.logging import logger

if TYPE_CHECKING:
    from tergite_tuner.backend import Hardware
    from tergite_tuner.config.session import SessionContext


def get_coupler_roles(session: "SessionContext") -> dict[str, dict[str, str]]:
    """Each coupler's control and target qubits, as the CZ schedules' ``coupler_dict``."""
    records = session.redis_store.find_many(collection="couplers", pks=session.couplers)
    try:
        return {
            coupler: {
                "control_qubit": record["control_qubit"],
                "target_qubit": record["target_qubit"],
            }
            for coupler, record in records["couplers"].items()
        }
    except KeyError:
        logger.warning(
            f"Some couplers control and target qubits are missing: {records}"
        )
        raise


def get_coupler_keywords(session: "SessionContext") -> dict[str, Any]:
    return {"coupler_dict": get_coupler_roles(session)}


def get_coupler_value(coupler: str, field: str, session: "SessionContext") -> Any:
    return session.redis.hget(f"couplers:{coupler}", field)


def get_phase_path(
    coupler: str, session: "SessionContext"
) -> Literal["via_02", "via_20"]:
    return get_coupler_value(coupler, "cz_phase_path", session)


def get_transition_frequency(coupler: str, session: "SessionContext") -> float:
    """The CZ's AC frequency on the coupler's phase path, rounded down to 10 kHz."""
    roles = get_coupler_roles(session)[coupler]
    control = session.redis_store.find_one("transmons", roles["control_qubit"])
    target = session.redis_store.find_one("transmons", roles["target_qubit"])
    control_f01 = float(control["clock_freqs"]["f01"])
    target_f01 = float(target["clock_freqs"]["f01"])
    phase_path = get_phase_path(coupler, session)
    if phase_path == "via_20":
        frequency = np.abs(target_f01 - float(control["clock_freqs"]["f12"]))
    elif phase_path == "via_02":
        frequency = np.abs(control_f01 - float(target["clock_freqs"]["f12"]))
    else:
        raise ValueError("Invalid Phase path")
    frequency = int(frequency / 1e4) * 1e4
    logger.info(f"{frequency / 1e6 = } MHz for coupler: {coupler}")
    return frequency


def set_dc_currents(
    hardware: "Hardware", point: Mapping[str, Mapping[str, Any]], _index: int
) -> None:
    """Sets each coupler's current of the external point, unless recalibrating."""
    if not hardware.session.is_recalibration:
        hardware.spi.set_dac_current(dict(point["dc_currents"]))


def reset_dc_currents(hardware: "Hardware") -> None:
    logger.info("Final Operation")
    hardware.spi.set_dac_current(dict.fromkeys(hardware.spi.dacs_dictionary, 0))


def get_random_shots(
    sweeps: Mapping[str, np.ndarray], loops: int, settings: tuple[str, ...]
) -> np.ndarray:
    """Uniformly random IQ shots, with an axis per setting and then the loops."""
    rng = np.random.default_rng(0)
    shape = (*(np.size(sweeps[setting]) for setting in settings), loops)
    return rng.uniform(-1, 1, shape) + 1j * rng.uniform(-1, 1, shape)
