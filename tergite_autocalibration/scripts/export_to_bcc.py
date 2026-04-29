# # This code is part of Tergite
# #
# # (C) Copyright Chalmers Next Labs AB 2025, 2026
# #
# # This code is licensed under the Apache License, Version 2.0. You may
# # obtain a copy of this license in the LICENSE.txt file in the root directory
# # of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
# #
# # Any modifications or derivative works of this code must retain this
# # copyright notice, and modified files need to carry a notice indicating
# # that they have been altered from the originals.
#
#
# from enum import Enum
# from pathlib import Path
# from typing import Tuple, Dict, Any, List, Type, Union
#
# import tomlkit
#
# from tergite_autocalibration.config.globals import REDIS_CONNECTION
#
#
# class _DataSource(Enum):
#     REDIS = "REDIS"
#     LITERAL = "LITERAL"
#
#
# _readout_resonator_parameters = [
#     ("acq_delay", "measure:acq_delay", _DataSource.REDIS, float),
#     ("acq_integration_time", "measure:integration_time", _DataSource.REDIS, float),
#     ("frequency", "extended_clock_freqs:readout_2state_opt", _DataSource.REDIS, float),
#     ("pulse_delay", "measure:ro_pulse_delay", _DataSource.REDIS, float),
#     ("pulse_duration", "measure:pulse_duration", _DataSource.REDIS, float),
#     ("pulse_type", "Square", _DataSource.LITERAL, str),
#     ("pulse_amplitude", "measure_2state_opt:pulse_amp", _DataSource.REDIS, float),
# ]
