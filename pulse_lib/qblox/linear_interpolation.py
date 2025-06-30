import copy
from dataclasses import dataclass
from typing import Any

import numpy as np

from pulse_lib.segments.data_classes.data_IQ import IQ_data_single
from pulse_lib.segments.data_classes.data_pulse import OffsetRamp, custom_pulse_element


@dataclass
class Interpolate:
    """
    Interpolation interval.
    """
    start: float
    stop: float


class InterpolationCompiler:
    """
    Creates a collection of interpolation intervals from pulse elements.
    Pulses can be interpolation on an interval when the frequency of the sine wave
    is low (< 1 MHz) and there are no other high frequency sine waves or custom pulses.
    Interpolation intervals are cut in two when the slope of the ramp in the interval changes.
    """

    def __init__(self, sine_interpolation_step: int,
                 pulse_elements: list[Any]):
        """
        Args:
            sine_interpolation_step:
                If not None checks for low frequency ( < 1 MHz) sine waves that can be rendered
                with linear interpolation using step.
            elements:
                List with pulse elements

        Warning:
            The list with elements will be modified if sine waves need to be broken due to
            ramp slope changes.
        """
        self._step = sine_interpolation_step
        self._sections = []
        self._sine_start = -1
        self._sine_stop = -1
        self._current = None
        self._suspend_till = -1
        self._current_sines: list[IQ_data_single] = []
        self._new_elements: list[IQ_data_single] = []
        self._process_elements(pulse_elements)

    def _process_elements(self, elements: list[Any]):
        for ipulse, pulse in enumerate(elements):
            if isinstance(pulse, IQ_data_single):
                if ((0 < abs(pulse.frequency) <= 1e6)
                        and pulse.stop - pulse.start > 2 * self._step
                        and pulse.envelope is None):
                    # Pulse is candidate for interpolation.
                    # create a copy in advance of any modification of the pulse.
                    pulse = copy.copy(pulse)
                    elements[ipulse] = pulse
                    self._add_sine(pulse)
                else:
                    self._suspend(pulse.start, pulse.stop)
            elif isinstance(pulse, OffsetRamp):
                self._cut(pulse.start)
                self._cut(pulse.stop)
            elif isinstance(pulse, custom_pulse_element):
                self._suspend(pulse.start, pulse.stop)
            else:
                raise Exception(f"Unknown type {type(pulse)}")

        if len(self._new_elements) > 0:
            elements += self._new_elements
            elements.sort(key=lambda p: (p.start, p.order, p.stop))

    @property
    def sections(self):
        return self._sections

    def _add_sine(self, sine: IQ_data_single):
        # Possibly multiple overlapping sines and possible multiple breaks and resumes of interpolation.
        # only start and stop of total matter...
        start = sine.start
        stop = sine.stop
        start = max(start, self._suspend_till)
        stop = max(stop, self._suspend_till)
        if stop - start < 2 * self._step:
            # too short for interpolation.
            return
        self._current_sines.append(sine)
        if start < self._sine_stop:
            if start < self._sine_start:
                raise Exception("Oops")
            self._sine_stop = max(self._sine_stop, stop)
        else:
            self._sine_start = start
            self._sine_stop = stop
            self._current = Interpolate(start, stop)
            self._sections.append(self._current)

    def _cut_sines(self, t):
        new_current_sines = []
        for pulse in self._current_sines:
            if pulse.start > t:
                raise Exception("Internal error: elements not sorted")
            if pulse.start == t:
                new_current_sines.append(pulse)
            elif pulse.stop > t:
                # break pulse in 2
                new_pulse = IQ_data_single(
                            start=t,
                            stop=pulse.stop,
                            amplitude=pulse.amplitude,
                            frequency=pulse.frequency,
                            phase_offset=pulse.phase_offset + pulse.frequency*2*np.pi*(t-pulse.start)*1e-9,
                            envelope=None,
                            ref_channel=None,
                            coherent_pulsing=False,
                            )
                pulse.stop = t

                self._new_elements.append(new_pulse)
                new_current_sines.append(new_pulse)

        self._current_sines = new_current_sines

    def _cut(self, t):
        # There is a cut for every OffsetRamp start and stop. And thus for every start/stop of sine, custom pulse...
        # Cuts are sequentially, incremental.
        self._cut_sines(t)
        current = self._current
        if current is not None and t != current.start:
            current.stop = t
            self._current = None
            if current.stop - current.start < 2 * self._step:
                # remove short section
                self._sections.pop()
        if t >= self._sine_start and current is None:
            if self._sine_stop - t > 2 * self._step:
                # start new section if long enough
                self._current = Interpolate(t, self._sine_stop)
                self._sections.append(self._current)

    def _suspend(self, start, stop):
        # called when sine frequency > 1 MHz or custom pulse.
        if self._current is not None:
            current = self._current
            current.stop = start
            self._current = None
            if current.stop - current.start < 2 * self._step:
                # remove short section
                self._sections.pop()
        if stop < self._sine_stop:
            self._sine_start = max(self._sine_start, stop)
        self._suspend_till = max(self._suspend_till, stop)
