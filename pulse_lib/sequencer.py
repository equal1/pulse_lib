import time
import logging
import uuid
from collections.abc import Sequence
from numbers import Number

import numpy as np
import matplotlib.pyplot as pt
from qcodes import Parameter

from .schedule.hardware_schedule import HardwareSchedule
from .segments.conditional_segment import conditional_segment
from .segments.data_classes.data_generic import parent_data
from .segments.segment_container import segment_container
from .segments.segment_measurements import measurement_acquisition
from .segments.utility.data_handling_functions import find_common_dimension
from .segments.utility.setpoint_mgr import setpoint_mgr, setpoint
from .segments.utility.looping import loop_obj
from .measurements_description import measurements_description
from .acquisition.acquisition_conf import AcquisitionConf
from .acquisition.player import SequencePlayer
from .acquisition.measurement_converter import MeasurementConverter, DataSelection, MeasurementParameter
from .compiler.condition_measurements import ConditionMeasurements


logger = logging.getLogger(__name__)


class sequencer():
    """
    Class to make sequences for segments.
    """

    def __init__(self, upload_module, digitizer_channels, awg_channels,
                 default_hw_schedule=None):
        '''
        make a new sequence object.
        Args:
            upload_module (uploader) : class of the upload module. Used to submit jobs
        Returns:
            None
        '''
        # each segment had its own unique identifier.
        self.id = uuid.uuid4()

        self._units = None
        self._setpoints = None
        self._names = None

        self._shape = (1,)
        self._sweep_index = [0]
        self.sequence = list()
        self.metadata = {}
        self.uploader = upload_module
        self._digitizer_channels = digitizer_channels
        self._awg_channels = awg_channels

        self._measurements_description = measurements_description(digitizer_channels)

        # arguments of post processing the might be needed during rendering.
        self.neutralize = True

        # hardware schedule (Keysight, Tektronix)
        self.hw_schedule = default_hw_schedule
        self.schedule_params = dict()
        if self.hw_schedule is not None:
            self.hw_schedule.set_schedule_parameters()

        self._n_rep = 1000
        self._sample_rate = 1e9
        self._alignment = None
        self._acquisition_conf = AcquisitionConf()
        self._measurement_converter = None
        self._total_time = None
        self._qubit_resonance_frequencies = {}

    @property
    def n_rep(self):
        '''
        Number times the sequence is repeated.
        If None or 0 the sequence is executed 1 time and the dimension 'repetition' will
        not be present in the measurement data.
        If n_rep is 1 then the dimension 'repetition' will be present in the measurement data.
        '''
        return self._n_rep

    @n_rep.setter
    def n_rep(self, value):
        if self._measurement_converter is not None:
            raise Exception('Cannot change n_rep after calling get_measurement_results or '
                            'get_measurement_param')
        self._n_rep = int(value) if value is not None else None

    @property
    def sweep_index(self):
        return self._sweep_index

    @property
    def shape(self):
        return self._shape

    @property
    def ndim(self):
        return len(self.shape)

    @property
    def setpoint_data(self):
        return self._setpoints

    @property
    def units(self):
        return self.setpoint_data.units

    @property
    def labels(self):
        return self.setpoint_data.labels

    @property
    def setpoints(self):
        return self.setpoint_data.setpoints

    @property
    def total_time(self):
        return self._total_time

    @property
    def sample_rate(self):
        return self._sample_rate

    @sample_rate.setter
    def sample_rate(self, rate):
        """
        Rate at which to set the AWG.

        Args:
            rate (float) : target sample rate for the AWG (unit : Sa/s).
        """
        self._sample_rate = self.uploader.get_effective_sample_rate(rate)

        msg = f"effective sampling rate is set to {self._sample_rate/1e6:.1f}MSa/s"
        logger.info(msg)
        print("Info : " + msg)

    @property
    def repetition_alignment(self):
        return self._alignment

    @repetition_alignment.setter
    def repetition_alignment(self, value):
        self._alignment = value

    @property
    def measurements_description(self):
        return self._measurements_description

    def _get_measurement_converter(self):
        if self._measurement_converter is None:
            n_rep = self.n_rep if not self._acquisition_conf.average_repetitions else None
            self._set_num_samples()
            self._measurements_description.calculate_measurement_offsets()
            self._measurement_converter = MeasurementConverter(self._measurements_description,
                                                               n_rep, self._acquisition_conf.sample_rate)
        return self._measurement_converter

    def add_sequence(self, sequence):
        '''
        Adds a sequence to this object.
        Args:
            sequence (array) : array of segment_container
        '''
        # check input
        for entry in sequence:
            if isinstance(entry, segment_container) or isinstance(entry, conditional_segment):
                self.sequence.append(entry)
            else:
                raise ValueError('The provided element in the sequence seems to be of the wrong data type.'
                                 f'{type(entry)} provided, segment_container expected')

        # update dimensionality of all sequence objects
        start = time.perf_counter()
        setpoint_data = setpoint_mgr()
        for seg_container in self.sequence:
            seg_container.enter_rendering_mode()
            self._shape = find_common_dimension(self._shape, seg_container.shape)
            setpoint_data += seg_container.setpoint_data
        logger.debug(f'Pre-render {(time.perf_counter()-start)*1000:.0f} ms')
        # Set the waveform cache equal to the sum over all channels and segments of the max axis length.
        # The cache will than be big enough for 1D iterations along every axis. This gives best performance
        total_axis_length = 0
        n_samples = 0
        for seg_container in self.sequence:
            sr = seg_container.sample_rate if seg_container.sample_rate else 1e9
            n_samples = max(n_samples, np.max(seg_container.total_time) * 1e9 / np.max(sr))
            if not isinstance(seg_container, conditional_segment):
                for channel_name in seg_container.channels:
                    shape = seg_container[channel_name].data.shape
                    total_axis_length += max(shape)
            else:
                for branch in seg_container.branches:
                    for channel_name in branch.channels:
                        shape = branch[channel_name].data.shape
                        total_axis_length += max(shape)
        # limit cache to 8 GB
        max_cache = int(1e9 / n_samples)
        cache_size = min(total_axis_length, max_cache)
        logger.debug(f'waveform cache: {cache_size} waveforms of max {n_samples} samples')
        parent_data.set_waveform_cache_size(cache_size)

        self._setpoints = setpoint_data
        self._shape = tuple(self._shape)
        self._sweep_index = [0]*self.ndim

        dig_awg_delay = self._calculate_max_dig_delay()
        self._condition_measurements = ConditionMeasurements(self._measurements_description,
                                                             self.uploader,
                                                             dig_awg_delay)

        t_tot = np.zeros(self.shape)

        for seg_container in self.sequence:
            self._condition_measurements.add_segment(seg_container, t_tot)
            self._measurements_description.add_segment(seg_container, t_tot)
            t_tot += seg_container.total_time
        self._total_time = t_tot
        self._condition_measurements.check_feedback_timing()
        self._generate_sweep_params()
        self._create_metadata()
        logger.debug('Done pre-compile')

    def recompile(self):
        ''' Recompiles the sequence applying new virtual matrix, attenuation, and delays.
        Note: No changes should be made on the segments. Only pulse-lib settings may be changed.
        '''
        for seg_container in self.sequence:
            seg_container.exit_rendering_mode()
            seg_container.enter_rendering_mode()

    def _calculate_max_dig_delay(self):
        '''
        Returns the maximum configured delay from AWG channel to digitizer channel.
        '''
        if not self._awg_channels or not self._digitizer_channels:
            return 0
        awg_delays = []
        for channel in self._awg_channels.values():
            awg_delays.append(channel.delay)

        dig_delays = []
        for channel in self._digitizer_channels.values():
            dig_delays.append(channel.delay)

        return max(dig_delays) - min(awg_delays)

    def _generate_sweep_params(self):
        self.params = []

        for i in range(len(self.labels)):
            par_name = self.setpoint_data.names[i].replace(' ', '_')
            set_param = index_param(par_name, self.labels[i], self.units[i], self, dim=i)
            self.params.append(set_param)
            setattr(self, par_name, set_param)
        self._original_params = self.params

    def _create_metadata(self):
        for i, pc in enumerate(self.sequence):
            md = pc.get_metadata()
            self.metadata[('pc%i' % i)] = md
        LOdict = {}
        for iq in self.sequence[0]._IQ_channel_objs:
            for vm in iq.qubit_channels:
                name = vm.channel_name
                LOdict[name] = iq.LO
        self.metadata['LOs'] = LOdict
        axis_info = {}
        for i, param in enumerate(self.params):
            axis_info[param.name] = {
                "axis": i,
                "values": param.values,
                "unit": param.unit,
                "label": param.label,
                }
        if axis_info:
            self.metadata["axes"] = axis_info

    def reorder_sweep_axis(self, new_order: list[int | Ellipsis.__class__] | list[str | Ellipsis.__class__]):
        """
        new_order can specify the full axis list, but also innermost and outermost separated by Ellipsis.
        Note: params order is inner loop to outer loop. Thus by default: [param_a(axis=0), param_b(axis=1), ...]
        """
        n_params = len(self.params)
        initial_indexes = list(range(n_params))
        param_names = [p.name for p in self._original_params]
        head = []
        tail = []
        insert = head
        for i in new_order:
            if isinstance(i, int):
                insert.append(i)
                initial_indexes.remove(i)
            elif isinstance(i, str):
                index = param_names.index(i)
                insert.append(index)
                initial_indexes.remove(index)
            elif i is Ellipsis:
                if insert == tail:
                    raise Exception("Only 1 Ellipsis is allowed in order")
                insert = tail

        self.params = [self._original_params[i] for i in (head + initial_indexes + tail)]

        self._create_metadata()

    def voltage_compensation(self, compensate):
        '''
        add a voltage compensation at the end of the sequence
        Args:
            compensate (bool) : compensate yes or no (default is True)
        '''
        self.neutralize = compensate

    def set_hw_schedule(self, hw_schedule: HardwareSchedule, **kwargs):
        '''
        Sets hardware schedule for the sequence.
        Args:
            hw_schedule: object with load() and start() methods to load and start the hardware schedule.
            kwargs : keyword arguments to be passed to the schedule.
        '''
        self.hw_schedule = hw_schedule
        self.hw_schedule.set_schedule_parameters(**kwargs)

    def set_qubit_resonance_frequency(self, qubit_channel_name, frequency):
        '''
        Sets qubit resonance frequency for this sequence.
        Args:
            qubit_channel_name (str): name of qubit channel
            frequency (float or loopobj): frequency for the qubit.
        '''
        if isinstance(frequency, loop_obj):
            if len(frequency.axis) != 1:
                raise Exception('Only 1D loops can be added')
            axis = frequency.axis[0]
            loop_shape = (len(frequency.setvals[0]),) + (1,)*(axis)
            # add to shape and setpoints
            self._shape = np.broadcast_shapes(self._shape, loop_shape)
            self._setpoints += setpoint(
                    axis,
                    name=(frequency.names[0],),
                    label=(frequency.labels[0],),
                    unit=(frequency.units[0],),
                    setpoint=(frequency.setvals[0],))
            self._generate_sweep_params()
        self._qubit_resonance_frequencies[qubit_channel_name] = frequency

    @property
    def configure_digitizer(self):
        return self._acquisition_conf.configure_digitizer

    @configure_digitizer.setter
    def configure_digitizer(self, enable):
        self._acquisition_conf.configure_digitizer = enable

    def set_acquisition(self,
                        t_measure=None,
                        sample_rate=None,
                        channels=[],
                        average_repetitions=None,
                        aggregate_func=None,
                        f_sweep: tuple[float, float] | None = None,
                        ):
        '''
        Args:
            t_measure (Union[float, loop_obj]):
                measurement time in ns. If None it must be specified in the acquire() call.
            sample_rate (float):
                Output data rate in Hz. When not None, the data should not be averaged,
                but sampled with specified rate. Useful for time traces and Elzerman readout.
                Does not change digitizer DAC rate. Data is down-sampled using block averages.
            average_repetitions (bool): Average data over the sequence repetitions.
            aggregate_func:
                Function aggregating data on time axis to new value. Must be used with sample_rate.
            f_sweep:
                If not None this specifies the start and stop (inclusive) frequencies for a frequency sweep
                on the digitizer frequency (and rf_source frequency).
                Currently only supported on Qblox.
        '''
        if self._measurement_converter is not None:
            raise Exception('Acquisition parameters cannot be changed after calling  '
                            'get_measurement_results or get_measurement_param')
        conf = self._acquisition_conf
        if t_measure:
            conf.t_measure = t_measure
        if sample_rate:
            conf.sample_rate = sample_rate
        if channels != []:
            conf.channels = channels
        if average_repetitions is not None:
            conf.average_repetitions = average_repetitions
        if aggregate_func is not None:
            conf.aggregate_func = aggregate_func
        if f_sweep is not None:
            if conf.sample_rate is None:
                raise Exception("sample rate must be set for frequency sweep")
            conf.f_sweep = f_sweep

    def _set_num_samples(self):
        default_t_measure = self._acquisition_conf.t_measure
        sample_rate = self._acquisition_conf.sample_rate
        for m in self._measurements_description.measurements:
            if not isinstance(m, measurement_acquisition):
                continue
            if m.n_repeat is not None:
                m.n_samples = m.n_repeat
                if sample_rate is not None:
                    logger.info(f'Ignoring sample_rate for measurement {m.name} because n_repeat is set')
            elif sample_rate is not None:
                if m.t_measure is None:
                    if default_t_measure is None:
                        raise Exception(f't_measure not specified for measurement {m}')
                    t_measure = default_t_measure
                elif isinstance(m.t_measure, Number):
                    t_measure = m.t_measure
                    # if t_measure = -1, then measure till end of sequence. (time trace feature)
                    if t_measure < 0:
                        t_measure = self.total_time - self._measurements_description.start_times[m.name]
                else:
                    raise Exception(f't_measure must be number and not a {type(m.t_measure)} for time traces')
                # @@@ implement Tektronix
                if hasattr(self.uploader, 'actual_acquisition_points'):
                    if isinstance(t_measure, Number):
                        m.n_samples, m.interval = self.uploader.actual_acquisition_points(m.acquisition_channel,
                                                                                          t_measure, sample_rate)
                    else:
                        m.n_samples = np.zeros(t_measure.shape, dtype=int)
                        for i, t in enumerate(t_measure.flat):
                            m.n_samples.flat[i], m.interval = \
                                self.uploader.actual_acquisition_points(m.acquisition_channel,
                                                                        t, sample_rate)
                else:
                    print(f'WARNING {type(self.uploader)} is missing method actual_acquisition_points();'
                          ' using old computation')
                    m.n_samples = self.uploader.get_num_samples(
                            m.acquisition_channel, t_measure, sample_rate)
                    m.interval = round(1e9/sample_rate)
                m.aggregate_func = self._acquisition_conf.aggregate_func
            else:
                m.n_samples = 1
            if self._acquisition_conf.f_sweep is not None and np.all(m.n_samples > 0):
                m.f_sweep = self._acquisition_conf.f_sweep

    def get_measurement_param(self, name='seq_measurements', upload=None,
                              states=True, values=True,
                              selectors=False, total_selected=True, accept_mask=False,
                              iq_mode='Complex', iq_complex=None):
        '''
        Returns a qcodes MultiParameter with an entry per measurement, i.e. per acquire call.
        The data consists of raw data and derived data.
        The arguments of this method and the acquire call determine
        which entries are present in the parameter.

        For a call `acquire(start, t_measure, ref=name, threshold=threshold,
        accept_if=condition)`, the parameter can contain the
        following entries:
            "{name}":
                Raw data of the acquire call in mV.
                1D array with length n repetitions not a time trace.
                When sample_rate is set with set_acquisition(sample_rate=sr),
                then the data contains time traces in a 2D array indexed
                [index_repetition][time_step].
                Only present when channel contains no IQ data or
                when `iq_complex=True` or `iq_mode in['Complex','I','Q','amplitude','phase']`.
            "{name}_I":
                Similar to "{name}", but contains I component of IQ.
                Only present when channel contains IQ data and `iq_mode='I+Q'`.
            "{name}_Q":
                Similar to "{name}", but contains Q component of IQ.
                Only present when channel contains IQ data and `iq_mode='I+Q'`.
            "{name}_amp":
                Similar to "{name}", but contains amplitude of IQ.
                Only present when channel contains IQ data and `iq_mode='amplitude+phase'`.
            "{name}_phase":
                Similar to "{name}", but contains phase of IQ.
                Only present when channel contains IQ data and `iq_mode='amplitude+phase'`.
            "{name}_state":
                Qubit states in 1 D array.
                Only present when `states=True`, threshold is set,
                and accept_if is None.
            "{name}_frac":
                Fraction of qubit states == 1 in scalar value in range [0, 1].
                A value is only added to this average when all selectors (accept_if)
                have the required value.
                Only present when `values=True`, threshold is set,
                and accept_if is None.
            "{name}_selected":
                The number of measurements matching the accept_if condition for
                the named acquisition.
                Only present when `selectors=True`, threshold is set,
                and accept_if is set.
            "total_selected":
                The number of accepted sequence shots.
                A shot is accepted when all selectors have the required value.
                Only present when there is a least 1 measurement with
                accept_if condition set, and `total_selected=True`.
            "mask":
                A 1D array indicating per shot whether it is accepted (1) or
                rejected (0).
                Only present when there is a least 1 measurement with
                accept_if condition set, and `accept_mask=True`.

        Args:
            name (str): name of the qcodes parameter.
            upload (str):
                If 'auto' uploads, plays and retrieves data.
                Otherwise only retrieves data.
            states (bool): If True return the qubit state after applying threshold.
            values (bool): If True returns the fraction of qubits with state = |1>.
            selectors (bool):
                If True returns the qubit state of the measurements that
                have the argument `accept_if` defined in the acquire call.
            total_selected (bool):
                If True returns the number of accepted sequence shots.
                A shot is accepted when all selectors have the required value.
            accept_mask (bool):
                If True returns per shot whether it is accepted or not.
            iq_mode (str):
                when channel contains IQ data, i.e. iq_input=True or frequency is not None,
                then this parameter specifies how the complex I/Q value should be returned:
                    'Complex': return IQ data as complex value.
                    'I': return only I value.
                    'Q': return only Q value.
                    'amplitude': return amplitude.
                    'phase:' return phase [radians],
                    'I+Q', return I and Q using channel name postfixes '_I', '_Q'.
                    'amplitude+phase'. return amplitude and phase using channel name postfixes '_amp', '_phase'.
            iq_complex (bool):
                If False this is equivalent to `iq_mode='I+Q'`

        '''
        if not self.configure_digitizer:
            raise Exception('configure_digitizer not set')
        # @@@ 'always' vs 'auto'
        if upload == 'auto':
            reader = SequencePlayer(self)
        else:
            reader = self
        mc = self._get_measurement_converter()
        if iq_complex is False:
            iq_mode = 'I+Q'
        selection = DataSelection(raw=True, states=states, values=values,
                                  selectors=selectors, total_selected=total_selected,
                                  accept_mask=accept_mask,
                                  iq_mode=iq_mode)
        param = MeasurementParameter(name, reader, mc, selection)
        return param

    def _retry_upload(self, exception, index):
        # '-8033' is a Keysight waveform upload error that requires a new upload
        if '(-8033)' in repr(exception):
            logger.info('Upload failure', exc_info=True)
            logger.warning(f'Sequence upload failed at index {index}; retrying...')
            return True
        return False

    def _retry_play(self, exception, index):
        # 'RT EXEC COMMAND UNDERFLOW' is a Qblox specific that requires a new play
        if 'RT EXEC COMMAND UNDERFLOW' in repr(exception):
            logger.info('Play failure', exc_info=True)
            logger.warning(f'Sequence play failed (Qblox: RT EXEC COMMAND UNDERFLOW) at index {index}; retrying...')
            return True
        if 'FORCED STOP' in repr(exception):
            logger.info('Play failure', exc_info=True)
            logger.warning(f'Sequence play failed (Qblox: spurious FORCED STOP) at index {index}; retrying...')
            return True
        return False

    def upload(self, index=None):
        '''
        Sends the sequence with the provided index to the uploader module.
        Args:
            index (tuple): index if wich you wannt to upload. If None the index set by sweep parameters is used.

        Remark that upload and play can run at the same time and it is best to
        start multiple uploads at once (during upload you can do playback, when the first one is finihsed)
        (note that this is only possible if you AWG supports upload while doing playback)
        '''
        if index is None:
            index = self.sweep_index[::-1]
        self._validate_index(index)
        n_retries = 2
        while True:
            try:
                upload_job = self.uploader.create_job(self.sequence, index, self.id,
                                                      self.n_rep, self._sample_rate,
                                                      self.neutralize, alignment=self._alignment)
                upload_job.set_acquisition_conf(self._acquisition_conf)
                upload_job.qubit_resonance_frequencies = self._qubit_resonance_frequencies
                if self.hw_schedule is not None:
                    upload_job.add_hw_schedule(self.hw_schedule, self.schedule_params)
                if self._condition_measurements.feedback_events:
                    upload_job.set_feedback(self._condition_measurements)

                self.uploader.add_upload_job(upload_job)
                return upload_job
            except Exception as ex:
                if n_retries <= 0:
                    raise
                if self._retry_upload(ex, index):
                    n_retries -= 1
                else:
                    raise

    def play(self, index=None, release=True):
        '''
        Playback a certain index, assuming the index is provided.
        Args:
            index (tuple): index if wich you wannt to upload. If None the index set by sweep parameters is used.
            release (bool) : release memory on the AWG after the element has been played.

        '''
        if index is None:
            index = self.sweep_index[::-1]
        self._validate_index(index)

        n_retries = 2
        while True:
            try:
                self.uploader.play(self.id, index, release)
                return
            except Exception as ex:
                if n_retries <= 0:
                    raise
                if self._retry_play(ex, index):
                    n_retries -= 1
                elif self._retry_upload(ex, index):
                    n_retries -= 1
                    # Retries are only done for Keysight and require a new upload of the waveform
                    self.upload(index)
                else:
                    raise

    def plot(self, index=None, segments=None, awg_output=True, channels=None):
        '''
        Plot sequence for specified index and segments.
        Args:
            index (tuple): index in sequence. If None use last index set via sweep params.
            segments (list[int]): indices of segments to plot. If None, plot all.
            awg_output (bool): if True plot output of AWGs, else plot virtual data.
            channels (list[str]): names of channels to plot, if None, plot all.
        '''
        if index is None:
            index = self.sweep_index[::-1]

        if segments is None:
            segments = range(len(self.sequence))
        for s in segments:
            seg = self.sequence[s]
            if isinstance(seg, conditional_segment):
                n_conditions = int(np.log2(len(seg.branches))+1e-8)
                for i, branch in enumerate(seg.branches):
                    pt.figure()
                    pt.title(f'Conditional segment {s}-{i:0{n_conditions}b} index:{index}')
                    branch.plot(index, channels=channels, render_full=awg_output)
            else:
                pt.figure()
                pt.title(f'Segment {s} index:{index}')
                seg.plot(index, channels=channels, render_full=awg_output)

    def get_measurement_results(self, index=None,
                                raw=True, states=True, values=True,
                                selectors=False, total_selected=True,
                                accept_mask=False, iq_mode='Complex',
                                iq_complex=None):
        '''
        Returns data per measurement, i.e. per acquire call.
        The data consists of raw data and derived data.
        The arguments of this method and the acquire call determine
        which keys are present in the returned dictionary.

        For a call `acquire(start, t_measure, ref=name, threshold=threshold,
        accept_if=condition)`, the returned dictionary can contain the
        following entries:
            "{name}":
                Raw data of the acquire call in mV.
                1D array with length n repetitions not a time trace.
                When sample_rate is set with set_acquisition(sample_rate=sr),
                then the data contains time traces in a 2D array indexed
                [index_repetition][time_step].
                Only present when channel contains no IQ data or
                when `iq_complex=True` or `iq_mode in['Complex','I','Q','amplitude','phase']`.
            "{name}_I":
                Similar to "{name}", but contains I component of IQ.
                Only present when channel contains IQ data,
                `raw=True`, and `iq_mode='I+Q'`.
            "{name}_Q":
                Similar to "{name}", but contains Q component of IQ.
                Only present when channel contains IQ data,
                `raw=True`, and `iq_mode='I+Q'`.
            "{name}_amp":
                Similar to "{name}", but contains amplitude of IQ.
                Only present when channel contains IQ data,
                `raw=True`, and `iq_mode='amplitude+phase'`.
            "{name}_phase":
                Similar to "{name}", but contains phase of IQ.
                Only present when channel contains IQ data,
                `raw=True`, and ``iq_mode='amplitude+phase'`.
            "{name}_state":
                Qubit states in 1 D array.
                Only present when `states=True`, threshold is set,
                and accept_if is None.
            "{name}_frac":
                Fraction of qubit states == 1 in scalar value in range [0, 1].
                A value is only added to this average when all selectors (accept_if)
                have the required value.
                Only present when `values=True`, threshold is set,
                and accept_if is None.
            "{name}_selected":
                The number of measurements matching the accept_if condition for
                the named acquisition.
                Only present when `selectors=True`, threshold is set,
                and accept_if is set.
            "total_selected":
                The number of accepted sequence shots.
                A shot is accepted when all selectors have the required value.
                Only present when there is a least 1 measurement with
                accept_if condition set, and `total_selected=True`.
            "mask":
                A 1D array indicating per shot whether it is accepted (1) or
                rejected (0).
                Only present when there is a least 1 measurement with
                accept_if condition set, and `accept_mask=True`.

        Args:
            index (tuple[int, ..]):
                index in sequence when sweeping parameters. If None uses
                the index of the last play call.
            raw (bool):
                If True return raw measurement data.
            states (bool): If True return the qubit state after applying threshold.
            values (bool): If True returns the fraction of qubits with state = |1>.
            selectors (bool):
                If True returns the qubit state of the measurements that
                have the argument `accept_if` defined in the acquire call.
            total_selected (bool):
                If True returns the number of accepted sequence shots.
                A shot is accepted when all selectors have the required value.
            accept_mask (bool):
                If True returns per shot whether it is accepted or not.
            iq_mode (str):
                when channel contains IQ data, i.e. iq_input=True or frequency is not None,
                then this parameter specifies how the complex I/Q value should be returned:
                    'Complex': return IQ data as complex value.
                    'I': return only I value.
                    'Q': return only Q value.
                    'amplitude': return amplitude.
                    'phase:' return phase [radians],
                    'I+Q', return I and Q using channel name postfixes '_I', '_Q'.
                    'amplitude+phase'. return amplitude and phase using channel name postfixes '_amp', '_phase'.
            iq_complex (bool):
                If False this is equivalent to `iq_mode='I+Q'`
        '''
        if index is None:
            index = self.sweep_index[::-1]
        mc = self._get_measurement_converter()
        mc.set_channel_data(self.get_channel_data(index), index)
        if iq_complex is False:
            iq_mode = 'I+Q'
        selection = DataSelection(raw=raw, states=states, values=values,
                                  selectors=selectors, total_selected=total_selected,
                                  accept_mask=accept_mask,
                                  iq_mode=iq_mode)
        return mc.get_measurements(selection)

    def get_channel_data(self, index=None):
        '''
        Returns acquisition data in mV per channel in a 1D or 2D array, depending
        on the average_repetitions setting and n_rep. See set_acquisition().

        Video mode will generally use average_repetitions = True and thus return 1D data.

        The 2D data is arranged as [index_repetition][index_sample].
        The data of all acquire calls in a sequence is concatenated to one array.
        The methods get_measurement_result() and get_measurement_param() return
        the data per acquire call.

        Args:
            index: If None, use last played sequence index.
        '''
        if not self.configure_digitizer:
            raise Exception('configure_digitizer not set')
        return self.uploader.get_channel_data(self.id, index)

    def close(self):
        '''
        Closes the sequencer and releases all memory and resources. Sequencer cannot be used anymore.
        '''
        if self.hw_schedule:
            self.hw_schedule.stop()
            # NOTE: unloading the schedule is a BAD idea. Uploading the Keysight schedule takes quite some time.
            # self.hw_schedule.unload()
            self.hw_schedule = None
        if not self.sequence:
            return
        for seg_container in self.sequence:
            seg_container.exit_rendering_mode()
        self.sequence = None
        self.uploader.release_memory(self.id)

    def release_memory(self, index=None):
        '''
        Releases waveform memory on AWG and PC.
        The sequencer also automatically releases the memory, but this can be delayed.
        Args:
            index (tuple) : index if wich you want to release. If none release memory for all indexes.
        '''
        if index is not None:
            self._validate_index(index)
        self.uploader.release_memory(self.id, index)

    def set_sweep_index(self, dim, value):
        self._sweep_index[dim] = value

    def __del__(self):
        logger.debug(f'destructor seq: {self.id}')
        self.release_memory()

    def _validate_index(self, index):
        '''
        Raises an exception when the index is not valid.
        '''
        if len(index) != len(self._shape):
            raise Exception(f'Index {index} does not match sequence shape {self._shape}')
        if any(i >= s for i, s in zip(index, self._shape)):
            raise IndexError(f'Index {index} out of range; sequence shape {self._shape}')


class index_param(Parameter):
    def __init__(self, name, label, unit, my_seq, dim):
        self.my_seq = my_seq
        self.dim = dim
        self.values = my_seq.setpoints[dim]
        val_map = dict(zip(self.values, range(len(self.values))))
        super().__init__(
                name=name,
                label=label,
                unit=unit,
                val_mapping=val_map,
                initial_value=self.values[0],
                )

    def snapshot_base(self,
                      update: bool | None = True,
                      params_to_skip_update: Sequence[str] | None = None):
        snapshot = super().snapshot_base(update=update, params_to_skip_update=params_to_skip_update)
        snapshot["values"] = self.values
        return snapshot

    def set_raw(self, value):
        self.my_seq.set_sweep_index(self.dim, value)
