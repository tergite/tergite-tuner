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

from tergite_tuner.backend import ExtendedTransmon
from tergite_tuner.backend.transmon import READOUTS


def test_each_readout_measures_on_its_clock_and_thresholds_where_listed():
    ExtendedTransmon.close_all()
    transmon = ExtendedTransmon("q00")
    try:
        operations = transmon.generate_device_config().elements["q00"]
    finally:
        transmon.close()

    for name, readout in READOUTS.items():
        kwargs = operations[name].factory_kwargs
        assert kwargs["clock"] == f"q00.{readout.clock}"
        assert ("acq_threshold" in kwargs) == readout.should_threshold
        labels = operations[name].gate_info_factory_kwargs
        assert ("feedback_trigger_label" in labels) == readout.should_label_feedback
