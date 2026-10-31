# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2023, 2025
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.


from typing import Iterable

import numpy


def samplespace_dimensions(samplespace: dict, loops=None) -> list[int]:
    """The size of each swept setting, and of the loops, as a dataset is shaped.

    example of a samplespace:
    samplespace = {
          'frequencies': {
             'q1': np.array([4.0e9, 4.1e9, 4.2e9]),
             'q2': np.array([4.5e9, 4.6e9, 4.7e9]),
           },
         'amplitudes': {
             'q1': np.array([0.1,0.2,0.3,0.4,0.5]),
             'q2': np.array([0.2,0.3,0.4,0.5,0.6]),
           }
    }
    the resulting dimensions are then [3,5]

    Args:
        samplespace: each swept setting's values, by element; every element has as
            many values as the first.
        loops: the number of loops, a last dimension if given.

    Returns:
        A dimension per setting, in order, then the loops.
    """
    dimensions = []
    settable_quantities = samplespace.keys()

    for quantity in settable_quantities:
        # keeping the first element, ASSUMING that all settable elements
        # have the same dimensions on their samplespace
        first_element = list(samplespace[quantity].keys())[0]  # 'q1' in the example
        # the array of frequencies or amplitudes in the example:
        settable_values = samplespace[quantity][first_element]
        if not isinstance(settable_values, Iterable):
            settable_values = numpy.array([settable_values])
        dimensions.append(len(settable_values))

    if loops is not None:
        dimensions.append(loops)
    return dimensions
