# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

from tergite_tuner import extract_bcc_params

extract_bcc_params(
    qubits = ["q11", "q12", "q13", "q14", "q15"],
    couplers = ["q11_q12", "q12_q13", "q13_q14" , "q14_q15"],
    env_file=".env", format="toml", output="calibration_seed.toml")