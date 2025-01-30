from dataclasses import dataclass
from typing import Callable

import numpy as np

from .utility.measurement_ref import MeasurementExpressionBase, MeasurementRef


@dataclass
class measurement_base:
    name: str | None
    accept_if: bool | None


@dataclass
class measurement_acquisition(measurement_base):
    acquisition_channel: str
    index: int
    threshold: float | None = None
    zero_on_high: bool = False
    ref: MeasurementRef | None = None
    t_measure: float | None = None
    n_repeat: int | None = None
    interval: float | None = None  # [ns]
    n_samples: int | None = None  # @@@ can be np.ndarray
    '''  Number of samples when using time traces. Value set by sequencer when downsampling. '''
    data_offset: int = 0  # @@@ can be np.ndarray
    ''' Offset of data in acquired channel data. '''
    aggregate_func: Callable[[float, np.ndarray], np.ndarray] = None  # @@@ t_start can be np.ndarray
    '''
    Function aggregating data on time axis to new value.
    '''
    f_sweep: tuple[float, float] | None = None
    """ frequency sweep start, stop values. stop is inclusive. Values set by sequencer. """

    @property
    def has_threshold(self):
        return self.threshold is not None


@dataclass
class measurement_expression(measurement_base):
    expression: MeasurementExpressionBase | None = None


# NOTE: this segment has no dimensions!


class segment_measurements:
    def __init__(self):
        self._measurements = []

    @property
    def measurements(self):
        return self._measurements

    def add_acquisition(self, channel: str, index: int,
                        t_measure: float | None,
                        threshold: float | None,
                        zero_on_high=False,
                        ref: MeasurementRef = None,
                        accept_if=None,
                        n_repeat=None,
                        interval=None):
        if ref is None:
            name = None
        elif isinstance(ref, str):
            name = ref
        else:
            name = ref.name
        self._measurements.append(measurement_acquisition(name, accept_if, channel, index,
                                                          threshold, zero_on_high, ref,
                                                          t_measure, n_repeat=n_repeat,
                                                          interval=interval))

    def add_expression(self, expression: MeasurementExpressionBase, accept_if=None, name: str = None):
        if name is None:
            name = f'<unnamed> {expression}'
        self._measurements.append(measurement_expression(name, accept_if, expression))

    def __getitem__(self, item):
        raise NotImplementedError()

    def __add__(self, other):
        if (len(self._measurements) > 0
                or len(other._measurements) > 0):
            raise Exception('Measurements cannot (yet) be combined')
        return self
