# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2023, 2024
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

from typing import Tuple

from tergite_autocalibration.utils.logging import logger


def draw_arrow_chart(header: str, node_list: list[str]):
    """
    Log the node sequence as a simple arrow chain.

    Args:
        header: Headline description
        node_list: Node sequence to print

    Returns:

    """
    if len(node_list) == 0:
        logger.status("Node sequence for the graph is empty.")
        return

    node_sequence = " \u2192 ".join(node_list)
    logger.info(f"{header}: {node_sequence}")


def print_measurement_info(duration: float, measurement: Tuple[int, int]) -> None:
    """Log information about the current measurement."""
    measurement_message = (
        f". Measurement {measurement[0] + 1} of {measurement[1]}"
        if measurement[1] > 1
        else ""
    )
    # Format the message with duration and the measurement message
    message = f"{duration:.2f} sec{measurement_message}"
    logger.info(f"schedule_duration = {message}")
