"""
File containing the parent class where all segment objects are derived from.
"""
import copy
import logging

import numpy as np
import matplotlib.pyplot as plt

from pulse_lib.segments.utility.data_handling_functions import loop_controller, use_end_time_cache
from pulse_lib.segments.data_classes.data_generic import data_container
from pulse_lib.segments.utility.looping import loop_obj
from pulse_lib.segments.utility.setpoint_mgr import setpoint_mgr
from pulse_lib.segments.data_classes.data_generic import map_index

logger = logging.getLogger(__name__)


class segment_base():
    '''
    Class defining base function of a segment. All segment types should support all operators.
    If you make new data type, here you should buil-in in basic support to allow for general operations.

    For an example, look in the data classes files.
    '''

    def __init__(self, name, data_object, segment_type='render'):
        '''
        Args:
            name (str): name of the segment usually the channel name
            data_object (object) : class that is used for saving the data type.
            segment_type (str) : type of the segment (e.g. 'render' --> to be rendered, 'virtual'--> no not render.)
        '''
        self.type = segment_type
        self.name = name
        self.render_mode = False
        # variable specifing the laetest change to the waveforms,

        # store data in numpy looking object for easy operator access.
        self.data = data_container(data_object)
        if use_end_time_cache:
            # end time for every index. Effectively this is a cache of data[index].end_time
            self._end_times = np.zeros(1)
        else:
            self._end_times = None

        # references to other channels (for virtual gates).
        self.reference_channels = []
        # reference channels for IQ virtual channels
        self.IQ_ref_channels = []
        self.references_markers = []
        # local copy of self that will be used to count up the virtual gates.
        self._pulse_data_all = None
        # data caching variable. Used for looping and so on (with a decorator approach)
        self.data_tmp = None
        self._pending_reset_time = None

        # setpoints of the loops (with labels and units)
        self._setpoints = setpoint_mgr()
        self.is_slice = False
        self._has_data = False

    @property
    def has_data(self):
        if not self._has_data:
            for d in self.data.flat:
                if d.has_data:
                    self._has_data = True
                    return True
        return False

    def _copy(self, cpy):
        cpy.type = copy.copy(self.type)
        cpy.data = copy.copy(self.data)
        if use_end_time_cache:
            cpy._end_times = self._end_times.copy()

        # note that the container objecet needs to take care of these. By default it will refer to the old references.
        cpy.reference_channels = copy.copy(self.reference_channels)
        cpy.IQ_ref_channels = copy.copy(self.IQ_ref_channels)
        cpy.references_markers = copy.copy(self.references_markers)

        # setpoints of the loops (with labels and units)
        cpy._setpoints = copy.copy(self._setpoints)

        return cpy

    @loop_controller
    def reset_time(self, time=None):
        '''
        resets the time back to zero after a certain point
        Args:
            time (double) : after time to reset back to 0. Note that this is absolute time and not rescaled time.
        '''
        self.data_tmp.reset_time(time)
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

    @loop_controller
    def wait(self, time, reset_time=False):
        '''
        resets the time back to zero after a certain point
        Args:
            time (double) : time in ns to wait
        '''
        if time < 0:
            raise Exception(f'Negative wait time {time} is not allowed')
        self.data_tmp.wait(time)
        if reset_time:
            self.data_tmp.reset_time(None)
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

        # To avoid unnecessary copying of data we first slice data,
        # set self.data=None, copy, and then restore data in self.
        # This trick makes the indexing operation orders faster.
        data_org = self.data
        self.data = None
        item = copy.copy(self)
        self.data = data_org

        item.data = data_item
        item.is_slice = True
        if use_end_time_cache:
            i = key[0]
            # Note: the numpy slice uses a writable view on the same memory!
            if len(self.shape) == 1:
                item._end_times = self._end_times[i:i+1]
            else:
                item._end_times = self._end_times[i]
        return item

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
            # drop axis that have length 1
            other_loopobj.add_data(data, axis=axes, dtype=object)
            self._setpoints += other._setpoints
            self.__add_segment(other_loopobj, time)
        else:
            self.__add_segment(other.data[0], time)

        return self

    @loop_controller
    def update_dim(self, loop_obj):
        '''
        update the dimesion of the segment by providing a loop object to it (decorator takes care of it).

        Args:
            loop_obj (loop_obj) : loop object with certain dimension to add.
        '''
        if not isinstance(loop_obj, float):
            raise Exception('update_dim failed. Reload pulselib!')
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
        # TODO @@@: split virtual voltage gates from IQ channels. Combining only needed for virtual voltage.
        '''
        pulse data object that contains the counted op data of all the reference channels (e.g. IQ and virtual gates).
        '''
        if self._pulse_data_all is None:
            if (len(self.reference_channels) == 0
                    and len(self.references_markers) == 0
                    and len(self.IQ_ref_channels) == 0):
                self._pulse_data_all = self.data
            else:
                self._pulse_data_all = copy.copy(self.data)
                for ref_chan in self.reference_channels:
                    self._pulse_data_all = self._pulse_data_all + ref_chan.segment.pulse_data_all*ref_chan.multiplication_factor
                for ref_chan in self.IQ_ref_channels:
                    self._pulse_data_all = self.pulse_data_all + ref_chan.virtual_channel.get_IQ_data(ref_chan.out_channel)
                for ref_chan in self.references_markers:
                    self._pulse_data_all = self._pulse_data_all + ref_chan.IQ_channel_ptr.get_marker_data()

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
                if self._pending_reset_time is not None:
                    return np.fmax(self._pending_reset_time, self._end_times)
                # use end time from numpy array instead of individual lookup of data elements.
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

    def get_segment(self, index, sample_rate=1e9, ref_channel_states=None):
        '''
        get the numpy output of as segment

        Args:
            index of segment (list) : which segment to render (e.g. [0] if dimension is 1 or [2,5,10] if dimension is 3)
            sample_rate (float) : #/s (number of samples per second)

        Returns:
            A numpy array that contains the points for each ns
            points is the expected lenght.
        '''
        if ref_channel_states:
            # Filter reference channels for use in data_pulse cache
            ref_channel_states = copy.copy(ref_channel_states)
            ref_channel_states.start_phases_all = None
            ref_names = [ref.virtual_channel.name for ref in self.IQ_ref_channels]
            ref_channel_states.start_phase = {key: value
                                              for (key, value) in ref_channel_states.start_phase.items()
                                              if key in ref_names}

        return self._get_data_all_at(index).render(sample_rate, ref_channel_states)

    def v_max(self, index, sample_rate=1e9):
        return self._get_data_all_at(index).get_vmax(sample_rate)

    def v_min(self, index, sample_rate=1e9):
        return self._get_data_all_at(index).get_vmin(sample_rate)

    def integrate(self, index, sample_rate=1e9):
        '''
        Get integral value of the waveform (e.g. to calculate an automatic compensation)

        Args:
            index (tuple) : index of the concerning waveform
            sample_rate (double) : rate at which to render the pulse

        Returns:
            integral (float) : integral of the pulse
        '''
        return self._get_data_all_at(index).integrate_waveform(sample_rate)

    def plot_segment(self, index=[0], render_full=True, sample_rate=1e9):
        '''
        Args:
            index : index of which segment to plot
            render full (bool) :
                do full render (e.g. also get data form virtual channels).
                Put True if you want to see the waveshape send to the AWG.
            sample_rate (float): standard 1 Gs/s
        '''
        if render_full is True:
            pulse_data_curr_seg = self._get_data_all_at(index)
        else:
            pulse_data_curr_seg = self.data[map_index(index, self.data.shape)]

        line = '-' if self.type == 'render' else ':'
        try:
            LO = self._qubit_channel.iq_channel.LO
        except Exception:
            LO = None

        y = pulse_data_curr_seg.render(sample_rate, LO=LO)
        x = np.linspace(0, pulse_data_curr_seg.total_time, len(y))
        plt.plot(x, y, line, label=self.name)
        plt.xlabel("time (ns)")
        plt.ylabel("amplitude (mV)")
        # plt.legend()

    def get_metadata(self):
        # Uses highest index of sequencer array (data_tmp)
        return self.data_tmp.get_metadata(self.name)
