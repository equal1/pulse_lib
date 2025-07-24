"""
File containing the parent class where all segment objects are derived from.
"""
import copy
import logging

import numpy as np
import matplotlib.pyplot as plt

from pulse_lib.segments.utility.data_handling_functions import loop_controller, use_end_time_cache
from pulse_lib.segments.data_classes.data_generic import data_container
from pulse_lib.segments.data_classes.data_acquisition import acquisition_data, acquisition
from pulse_lib.segments.utility.looping import loop_obj
from pulse_lib.segments.utility.setpoint_mgr import setpoint_mgr
from pulse_lib.segments.utility.measurement_ref import MeasurementRef
from pulse_lib.segments.segment_measurements import segment_measurements
from pulse_lib.segments.data_classes.data_generic import map_index

logger = logging.getLogger(__name__)


class segment_acquisition():
    '''
    Class defining base function of a segment. All segment types should support all operators.
    If you make new data type, here you should buil-in in basic support to allow for general operations.

    For an example, look in the data classes files.
    '''
    def __init__(self, name, measurement_segment:segment_measurements, segment_type = 'render'):
        '''
        Args:
            name (str): name of the segment usually the channel name
            segment_type (str) : type of the segment (e.g. 'render' --> to be rendered, 'virtual'--> no not render.)
        '''
        self.type = segment_type
        self.name = name
        self._measurement_segment = measurement_segment
        self._measurement_index = 0
        self._has_data = False

        # store data in numpy looking object for easy operator access.
        self.data = data_container(acquisition_data())
        if use_end_time_cache:
            self._end_times = np.zeros(1)
        else:
            self._end_times = None

        # local copy of self that will be used to count up the virtual gates.
        self._pulse_data_all = None
        # data caching variable. Used for looping and so on (with a decorator approach)
        self.data_tmp = None
        self._pending_reset_time = None

        # setpoints of the loops (with labels and units)
        self._setpoints = setpoint_mgr()
        self.render_mode = False
        self.is_slice = False

    @property
    def has_data(self):
        if not self._has_data:
            for d in self.data.flat:
                if d.has_data:
                    self._has_data = True
                    return True
        return False

    def acquire(self, start, t_measure=None, ref=None,
                n_repeat=None, interval=None,
                threshold=None, zero_on_high=False, accept_if=None,
                wait=False):
        '''
        Adds an acquisition.
        Args:
            start (float or loopobj): start time
            t_measure (None, float or loopobj): measurement time
            ref (Optional[str or MeasurementRef]): optional reference to retrieve measurement by name
            n_repeat (Optional[int]): number of repeated triggers, e.g for video mode
            interval (Optional[float]): repetition interval in ns when n_repeat is also set
            threshold (Optional[float]): optional threshold
            zero_on_high (bool): if True then result = 0 if value>threshold
            accept_if (Optional[bool]):
                if set the result of the sequence will only be accepted if the measurement
                equals this condition.
        '''
        if n_repeat is not None and interval is None:
            raise Exception('interval must be specified when n_repeat is set')
        # @@@ MAKE proper solution
        # if isinstance(ref, str):
        #     ref = MeasurementRef(ref)
        if isinstance(ref, MeasurementRef) and zero_on_high:
            ref.inverted()
        # TODO: measurements are not sorted in time. So, this works as long as they are added in right order.
        index = self._measurement_index
        self._measurement_index += 1
        self._measurement_segment.add_acquisition(self.name, index, t_measure,
                                                  threshold,
                                                  zero_on_high=zero_on_high,
                                                  ref=ref,
                                                  accept_if=accept_if,
                                                  n_repeat=n_repeat,
                                                  interval=interval)
        self._acquire(start, t_measure, ref=ref,
                      n_repeat=n_repeat, interval=interval,
                      threshold=threshold, zero_on_high=zero_on_high,
                      wait=wait)

    @loop_controller
    def _acquire(self, start, t_measure, ref=None,
                 n_repeat=None, interval=None,
                 threshold=None, zero_on_high=False,
                 wait=False):
        acq = acquisition(ref, start, t_measure,
                          n_repeat=n_repeat, interval=interval,
                          threshold=threshold, zero_on_high=zero_on_high)
        self.data_tmp.add_acquisition(acq, wait=wait)
        return self.data_tmp

    def append(self, other):
        '''
        Append a segment to the end of this segment.
        '''
        self.add(other, time=-1)

    def add(self, other, time=None):
        '''
        Add the other segment to this segment at specified time.
        Args:
            other (segment) : the segment to be appended
            time (double/loop_obj) : add at the given time. if None, append at t_start of the segment)
        '''
        if other.shape != (1,):
            data = other.data
            ndim = data.ndim
            axes = []
            for i, n in enumerate(data.shape, 1):
                if n > 1:
                    axes.append(ndim-i)
            data = np.squeeze(data)

            other_loopobj = loop_obj(no_setpoints=True)
            other_loopobj.add_data(data, axis=axes, dtype=object)
            self._setpoints += other._setpoints
            self.__add_segment(other_loopobj, time)
        else:
            self.__add_segment(other.data[0], time)

        for m in other._measurement_segment.measurements:
            if m.acquisition_channel == self.name:
                m_copy = copy.copy(m)
                m_copy.index = self._measurement_index
                self._measurement_segment._measurements.append(m_copy)
                self._measurement_index += 1

        return self

    @loop_controller
    def reset_time(self, time=None):
        '''
        resets the time back to zero after a certain point
        Args:
            time (double) : (optional), after time to reset back to 0. Note that this is absolute time and not rescaled time.
        '''
        self.data_tmp.reset_time(time)
        return self.data_tmp

    @loop_controller
    def wait(self, time, reset_time=False):
        '''
        resets the time back to zero after a certain point
        Args:
            time (double) : time in ns to wait
        '''
        self.data_tmp.wait(time)
        if reset_time:
            self.data_tmp.reset_time(None)
        return self.data_tmp

    @loop_controller
    def update_end(self, stop):
        '''
        Sets the end of the segment to at least stop (relative to current start time).
        This has an effect similar to add_block(0, stop, 0.0), but works on all
        Args:
            stop (float) : minimum end time of segment.
        '''
        self.data_tmp.update_end_time(stop)
        return self.data_tmp

    @property
    def setpoints(self):
        return self._setpoints


    def __getitem__(self, *key):
        '''
        get slice or single item of this segment (note no copying, just referencing)
        Args:
            *key (int/slice object) : key of the element -- just use numpy style accessing (slicing supported)
        '''
        data_item = self.data[key[0]]
        if not isinstance(data_item, data_container):
            # If the slice contains only 1 element, then it's not a data_container anymore.
            # Put it in a data_container to maintain pulse_lib structure.
            data_item = data_container(data_item)

        # To avoid unnecessary copying of data we first slice data of self, set self.data = None,
        # copy, and then restore data in self.
        # This trick makes the indexing operation orders faster.
        data_org = self.data
        self.data = None
        item = copy.copy(self)
        self.data = data_org

        item.data = data_item
        if use_end_time_cache:
            i = key[0]
            # Note: the numpy slice uses the same memory!
            if len(self.shape) == 1:
                item._end_times = self._end_times[i:i+1]
            else:
                item._end_times = self._end_times[i]
        item.is_slice = True
        return item


    @loop_controller
    def repeat(self, number):
        '''
        repeat a waveform n times.

        Args:
            number (int) : number of ties to repeat the waveform
        '''

        data_copy = copy.copy(self.data_tmp)
        for i in range(number-1):
            self.data_tmp.append(data_copy)

        return self.data_tmp

    @loop_controller
    def update_dim(self, loop_obj):
        '''
        update the dimesion of the segment by providing a loop object to it (decorator takes care of it).

        Args:
            loop_obj (loop_obj) : loop object with certain dimension to add.
        '''
        return self.data_tmp

    @loop_controller
    def __add_segment(self, other, time):
        """
        Add segment to this one. If time is not specified it will be added at start-time.

        Args:
            other (segment_base) : the segment to be appended
            time: time to add the segment.
        """
        self.data_tmp.add_data(other, time)
        return self.data_tmp

    # ==== getters on all_data

    @property
    def pulse_data_all(self):
        '''
        pulse data object that contains the counted op data of all the reference channels (e.g. IQ and virtual gates).
        '''
        if self._pulse_data_all is None:
            self._pulse_data_all = copy.copy(self.data)

        return self._pulse_data_all

    @property
    def shape(self):
        if not self.render_mode:
            return self.data.shape
        else:
            return self.pulse_data_all.shape

    @property
    def ndim(self):
        if not self.render_mode:
            return self.data.ndim
        else:
            return self.pulse_data_all.shape

    @property
    def total_time(self):
        if not self.render_mode:
            if use_end_time_cache:
                # use end time from numpy array instead of individual lookup of data elements.
                if self._pending_reset_time is not None:
                    return np.fmax(self._pending_reset_time, self._end_times)
                return self._end_times
            else:
                return self.data.total_time
        else:
            return self.pulse_data_all.total_time

    @property
    def start_time(self):
        if not self.render_mode:
            return self.data.start_time
        else:
            return self.pulse_data_all.start_time

    def enter_rendering_mode(self):
        self.render_mode = True
        # make a pre-render of all the pulse data (e.g. compose channels, do not render in full).
        if self.type == 'render':
            self.pulse_data_all

    def exit_rendering_mode(self):
        self.render_mode = False
        self._pulse_data_all = None

    # ==== operations working on an index

    def _get_data_all_at(self, index):
        return self.pulse_data_all[map_index(index, self.shape)]

    def plot_segment(self, index = [0], render_full = True, sample_rate = 1e9):
        '''
        Args:
            index : index of which segment to plot
            render full (bool) : do full render (e.g. also get data form virtual channels). Put True if you want to see the waveshape send to the AWG.
            sample_rate (float): standard 1 Gs/s
        '''
        if render_full == True:
            pulse_data_curr_seg = self._get_data_all_at(index)
        else:
            pulse_data_curr_seg = self.data[map_index(index, self.shape)]

        y = pulse_data_curr_seg.render(sample_rate)
        x = np.linspace(0, pulse_data_curr_seg.total_time, len(y))
        # plot with markers only
        plt.plot(x, y, '>', label=self.name)
        plt.xlabel("time (ns)")
        plt.ylabel("amplitude (mV)")
        plt.legend()

    def get_metadata(self):
        return self.data_tmp.get_metadata(self.name)