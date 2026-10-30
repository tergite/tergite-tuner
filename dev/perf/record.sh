#!/usr/bin/env bash
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
#
# Records the performance measures into <dir>, from the repository root:
#   dev/perf/record.sh <dir>
# then compare them with the baseline:
#   uv run python -m dev.perf.compare dev/perf/baselines/<machine> <dir>
set -euo pipefail

directory="$1"
mkdir -p "$directory"
uv run --locked pytest dev/perf -q -p no:cacheprovider --perf-json="$directory/nodes.json"
uv run --locked python -m dev.perf.record_runs "$directory/runs.json"
printf 'commit %s\nmachine %s\n' "$(git rev-parse --short HEAD)" "$(uname -sm)" > "$directory/machine.txt"
