import time
from uuid import UUID
from datetime import datetime
import numpy as np
import logging
import math
from dataclasses import dataclass, field
from typing import Dict, Optional, List, Union
from numbers import Number

from .rendering import SineWaveform, get_modulation
from .pulsar_sequencers import (
        Voltage1nsSequenceBuilder,
        VoltageSequenceBuilder,
        IQSequenceBuilder,
        AcquisitionSequenceBuilder,
        SequenceBuilderBase,
        PulsarConfig)

from q1pulse import Q1Instrument

from pulse_lib.segments.data_classes.data_IQ import IQ_data_single, Chirp
from pulse_lib.segments.data_classes.data_pulse import (
        PhaseShift, custom_pulse_element, OffsetRamp)
from pulse_lib.uploader.uploader_funcs import get_iq_nco_idle_frequency, merge_markers

logger = logging.getLogger(__name__)

def iround(value):
    return math.floor(value+0.5)


class PulsarUploader:
    verbose = False
    output_dir = None
    resolution_1ns = True

    def __init__(self, awg_devices, awg_channels, marker_channels,
                 IQ_channels, qubit_channels, digitizers, digitizer_channels):
        self.awg_channels = awg_channels
        self.marker_channels = marker_channels
        self.IQ_channels = IQ_channels
        self.qubit_channels = qubit_channels
        self.digitizer_channels = digitizer_channels

        self.jobs = []
        self.acq_description = None

        q1 = Q1Instrument(PulsarUploader.output_dir, add_traceback=False)
        self.q1instrument = q1

        for awg in awg_devices.values():
            q1.add_qcm(awg)
        for module in digitizers.values():
            # QRM is passed as digitizer
            q1.add_qrm(module)

        self._link_markers_to_seq()
        self._get_voltage_channels()

        for name, awg_ch in self.awg_voltage_channels.items():
            q1.add_control(name, awg_ch.awg_name, [awg_ch.channel_number])

        for name, qubit_ch in self.qubit_channels.items():
            iq_out_channels = qubit_ch.iq_channel.IQ_out_channels
            out_channels = [self.awg_channels[iq_out_ch.awg_channel_name]
                            for iq_out_ch in iq_out_channels]
            module_name = out_channels[0].awg_name
            # TODO @@@ check I and Q phase.
            q1.add_control(name, module_name, [out_ch.channel_number for out_ch in out_channels])

        for name, dig_ch in self.digitizer_channels.items():
            out_ch = []
            rf_source = dig_ch.rf_source
            if rf_source is not None:
                out = rf_source.output
                if out is str or len(out) != 2:
                    raise Exception(f'Resonator must be defined as (module_name,channel). '
                                    f'Format {out} is currently not supported for "{name}"')
                if out[0] != dig_ch.module_name:
                    raise Exception(f'Resonator must be on same module. '
                                    f'Format {out} is currently not supported for "{name}"')
                out_ch = [out[1]] if isinstance(out[1], int) else out[1]
            q1.add_readout(name, dig_ch.module_name, out_channels=out_ch)

        for name, marker_ch in self.marker_channels.items():
            # TODO implement marker channel inversion
            if marker_ch.invert:
                raise Exception(f'Marker channel inversion not (yet) supported')


    @staticmethod
    def set_output_dir(path):
        PulsarUploader.output_dir = path

    def _get_voltage_channels(self):
        iq_out_channels = []

        for IQ_channel in self.IQ_channels.values():
            iq_pair = IQ_channel.IQ_out_channels
            if len(iq_pair) != 2:
                raise Exception(f'IQ-channel should have 2 awg channels '
                                f'({iq_pair})')
            out_names = [self.awg_channels[ch_info.awg_channel_name] for ch_info in iq_pair]
            awg_names = [awg_channel.awg_name for awg_channel in out_names]

            if awg_names[0] != awg_names[1]:
                raise Exception(f'IQ channels should be on 1 awg: {iq_pair}')

            iq_out_channels += [ch_info.awg_channel_name for ch_info in iq_pair]

        self.awg_voltage_channels = {}
        for name, awg_channel in self.awg_channels.items():
            if name not in iq_out_channels:
                self.awg_voltage_channels[name] = awg_channel

    def _link_markers_to_seq(self):
        default_iq_markers = {}
        for iq_channel in self.IQ_channels.values():
            marker_channels = iq_channel.marker_channels
            I_channel_name = iq_channel.IQ_out_channels[0].awg_channel_name
            awg_module_name = self.awg_channels[I_channel_name].awg_name
            if len(iq_channel.qubit_channels) == 0:
                continue
            qubit_channel = iq_channel.qubit_channels[0]
            for marker_name in marker_channels:
                m_ch = self.marker_channels[marker_name]
                if awg_module_name == m_ch.module_name:
                    default_iq_markers[m_ch.name] = qubit_channel.channel_name

        seq_markers = {}
        marker_sequencers = []
        for channel_name, marker_channel in self.marker_channels.items():
            if marker_channel.sequencer_name is not None:
                seq_name = marker_channel.sequencer_name
            elif channel_name in default_iq_markers:
                seq_name = default_iq_markers[channel_name]
            else:
                seq_name = f'_M_{marker_channel.module_name}'
                marker_sequencers.append(seq_name)
                self.q1instrument.add_control(seq_name, marker_channel.module_name, channels=[])
            mlist = seq_markers.setdefault(seq_name, [])
            mlist.append(channel_name)

        self.seq_markers = seq_markers
        self.marker_sequencers = marker_sequencers


    @property
    def supports_conditionals(self):
        return False

    def get_effective_sample_rate(self, sample_rate):
        """
        Returns the sample rate that will be used by the AWG.
        """
        return 1e9

    def actual_acquisition_points(self, acquisition_channel, t_measure, sample_rate):
        return _actual_acquisition_points(t_measure, sample_rate)

    def create_job(self, sequence, index, seq_id, n_rep, sample_rate,
                   neutralize=True, alignment=None):
        # TODO @@@ implement alignment
        # remove any old job with same sequencer and index
        self.release_memory(seq_id, index)
        return Job(self.jobs, sequence, index, seq_id, n_rep, sample_rate, neutralize)

    def add_upload_job(self, job):
        '''
        add a job to the uploader.
        Args:
            job (upload_job) : upload_job object that defines what needs to be uploaded and possible post processing of the waveforms (if needed)
        '''
        '''
        Class taking care of putting the waveform on the right AWG.

        Steps:
        1) get all the upload data
        2) perform DC correction (if needed)
        3) convert data in an aprropriate upload format
        4) start upload of all data
        5) store reference to uploaded waveform in job
        '''
        start = time.perf_counter()

        self.jobs.append(job)

        aggregator = UploadAggregator(self.q1instrument, self.awg_channels,
                                      self.marker_channels, self.digitizer_channels,
                                      self.qubit_channels, self.awg_voltage_channels,
                                      self.marker_sequencers, self.seq_markers
                                      )

        aggregator.build(job)

        duration = time.perf_counter() - start
        logger.info(f'generated upload data {job.index} ({duration*1000:6.3f} ms)')
#        print(f'Generated upload data in {duration*1000:6.3f} ms')


    def __get_job(self, seq_id, index):
        """
        get job data of an uploaded segment
        Args:
            seq_id (uuid) : id of the sequence
            index (tuple) : index that has to be played
        Return:
            job (upload_job) :job, with locations of the sequences to be uploaded.
        """
        for job in self.jobs:
            if job.seq_id == seq_id and job.index == index and not job.released:
                return job

        logger.error(f'Job not found for index {index} of seq {seq_id}')
        raise ValueError(f'Sequence with id {seq_id}, index {index} not placed for upload .. . Always make sure to first upload your segment and then do the playback.')


    def play(self, seq_id, index, release_job = True):
        """
        start playback of a sequence that has been uploaded.
        Args:
            seq_id (uuid) : id of the sequence
            index (tuple) : index that has to be played
            release_job (bool) : release memory on AWG after done.
        """
        # set offset for output channels (also I/Q)
        for awg_channel in self.awg_channels.values():
            module = self.q1instrument.modules[awg_channel.awg_name]
            if awg_channel.offset is not None:
                module.set_out_offset(awg_channel.channel_number, awg_channel.offset)

        job =  self.__get_job(seq_id, index)
        channels = job.acquisition_conf.channels
        if channels is None:
            channels = self.digitizer_channels.keys()
        self.acq_description = AcqDescription(seq_id, index, channels,
                                              job.acq_data_scaling,
                                              job.n_rep,
                                              job.acquisition_conf.average_repetitions)

        logger.info(f'Play {index}')

        n_rep = job.n_rep if job.n_rep else 1
        total_seconds = job.playback_time * n_rep * 1e-9
        timeout_minutes = int(total_seconds*1.1 / 60) + 1

        # update resonator frequency and amplitude
        for ch_name, dig_channel in self.digitizer_channels.items():
            nco_freq = dig_channel.frequency
            if nco_freq is None:
                continue
            job.program[ch_name].nco_frequency = nco_freq

        self.q1instrument.start_program(job.program)
        self.q1instrument.wait_stopped(timeout_minutes=timeout_minutes)

        if release_job:
            job.release()

    def get_channel_data(self, seq_id, index):
        acq_desc = self.acq_description
        if (acq_desc.seq_id != seq_id
            or (index is not None and acq_desc.index != index)):
            raise Exception(f'Data for index {index} not available')

        result = {}
        for channel_name in acq_desc.channels:
            scaling = acq_desc.acq_data_scaling[channel_name]
            dig_ch = self.digitizer_channels[channel_name]
            in_ch = dig_ch.channel_numbers
            in_ranges = self.q1instrument.get_input_ranges(channel_name)

            if scaling is None:
                # Scaling is None when there are no acquisitions. @@@ TODO make clearer code.
                raw = [np.zeros(0)]*2
            else:
                try:
                    start = time.perf_counter()
                    bin_data = self.q1instrument.get_acquisition_bins(channel_name, 'default') # @@@ handle timeout
                    raw = []
                    for i in range(2):
                        path_data = np.require(bin_data['integration'][f'path{i}'], dtype=float)
                        # scale to mV values; in_range is voltage peak-peak
                        raw.append(self._scale_acq_data(path_data, in_ranges[i]/2*scaling*1000))
                    duration_ms = (time.perf_counter()-start)*1000
                    logger.debug(f'Retrieved data {channel_name} in {duration_ms:5.1f} ms')
                except KeyError:
                    raw = [np.zeros(0)]*2

            if dig_ch.frequency or len(in_ch) == 2:

                if dig_ch.frequency or dig_ch.iq_input:
                    # @@@ if frequency, set phase in QRM.sequencer phase_rotation_acq
                    raw_ch = (raw[0] + 1j * raw[1]) * np.exp(1j*dig_ch.phase)
                    if not dig_ch.iq_out:
                        raw_ch = raw_ch.real
                    result[channel_name] = raw_ch
                else:
                    if in_ch[0] == 1:
                        # swap results
                        raw[0], raw[1] = raw[1], raw[0]
                    result[f'{channel_name}_0'] = raw[0]
                    result[f'{channel_name}_1'] = raw[1]

            else:
                ch = in_ch[0]
                result[channel_name] = raw[ch]

        if not acq_desc.average_repetitions and acq_desc.n_rep:
            for key,value in result.items():
                result[key] = value.reshape((acq_desc.n_rep, -1))

        return result

    def _scale_acq_data(self, data, scaling):
        if len(data) == 0:
            return data
        if isinstance(scaling, Number):
            data *= scaling
            return data
        res = data.reshape((-1, len(scaling))) * scaling
        return res.flatten()

    def wait_until_AWG_idle(self):
        # @@@ TODO implement when run_program() has async version
        pass

    def release_memory(self, seq_id=None, index=None):
        """
        Release job memory for `seq_id` and `index`.
        Args:
            seq_id (uuid) : id of the sequence. if None release all
            index (tuple) : index that has to be released; if None release all.
        """
        for job in self.jobs:
            if (seq_id is None
                or (job.seq_id == seq_id and (index is None or job.index == index))):
                job.release()


    def release_jobs(self):
        for job in self.jobs:
            job.release()


@dataclass
class AcqDescription:
    seq_id: UUID
    index: List[int]
    channels: List[str]
    acq_data_scaling: Dict[str, Union[float, np.ndarray]]
    n_rep: int
    average_repetitions: bool = False


class Job(object):
    """docstring for upload_job"""
    def __init__(self, job_list, sequence, index, seq_id, n_rep, sample_rate, neutralize=True, priority=0):
        '''
        Args:
            job_list (list): list with all jobs.
            sequence (list of list): list with list of the sequence
            index (tuple) : index that needs to be uploaded
            seq_id (uuid) : if of the sequence
            n_rep (int) : number of repetitions of this sequence.
            sample_rate (float) : sample rate
            neutralize (bool) : place a neutralizing segment at the end of the upload
            priority (int) : priority of the job (the higher one will be excuted first)
        '''
        self.job_list = job_list
        self.sequence = sequence
        self.seq_id = seq_id
        self.index = index
        self.n_rep = n_rep
        self.default_sample_rate = sample_rate
        self.neutralize = neutralize
        self.priority = priority
        self.schedule_params = {}
        self.playback_time = 0 #total playtime of the waveform
        self.acquisition_conf = None
        self.acq_data_scaling = {}

        self.released = False

        logger.debug(f'new job {seq_id}-{index}')


    def add_hw_schedule(self, hw_schedule, schedule_params):
        """
        Add the scheduling to the AWG waveforms.
        args:
            hw_schedule (HardwareSchedule) : schedule for repetitively starting the AWG waveforms
            kwargs : keyword arguments for the hardware schedule (see usage in the examples)
        """
        self.hw_schedule = hw_schedule
        self.schedule_params = schedule_params

    def set_acquisition_conf(self, conf):
        self.acquisition_conf = conf

    def release(self):
        if self.released:
            logger.warning(f'job {self.seq_id}-{self.index} already released')
            return

        self.upload_info = None
        logger.debug(f'release job {self.seq_id}-{self.index}')
        self.released = True

        if self in self.job_list:
            self.job_list.remove(self)


    def __del__(self):
        if not self.released:
            logger.debug(f'Job {self.seq_id}-{self.index} was not released. '
                          'Automatic release in destructor.')
            self.release()


@dataclass
class ChannelInfo:
    # static data
    delay_ns: float = 0
    amplitude: float = 0
    attenuation: float = 1.0
    dc_compensation: bool = False
    dc_compensation_min: float = 0.0
    dc_compensation_max: float = 0.0
    bias_T_RC_time: Optional[float] = None
    # aggregation state
    integral: float = 0.0


@dataclass
class JobUploadInfo:
    dc_compensation_duration_ns: float = 0.0
    dc_compensation_voltages: Dict[str, float] = field(default_factory=dict)

@dataclass
class SegmentRenderInfo:
    # original times from sequence, cummulative start/end times
    # first segment starts at t_start = 0
    t_start: float
    t_end: float


def _actual_acquisition_points(t_measure, sample_rate):
    trigger_period = PulsarConfig.align(1e9/sample_rate)
    t_measure = PulsarConfig.align(t_measure)
    n_samples = t_measure // trigger_period
    return n_samples, trigger_period


class UploadAggregator:
    verbose = False

    def __init__(self, q1instrument, awg_channels, marker_channels, digitizer_channels,
                 qubit_channels, awg_voltage_channels, marker_sequencers, seq_markers):

        self.q1instrument = q1instrument
        self.awg_voltage_channels = awg_voltage_channels
        self.marker_channels = marker_channels
        self.digitizer_channels = digitizer_channels
        self.qubit_channels = qubit_channels
        self.marker_sequencers = marker_sequencers
        self.seq_markers = seq_markers

        self.channels = dict()

        delays = []
        for channel in awg_channels.values():
            info = ChannelInfo()
            self.channels[channel.name] = info

            info.attenuation = channel.attenuation
            info.delay_ns = channel.delay
            info.amplitude = None # channel.amplitude cannot be taken into account
            info.bias_T_RC_time = channel.bias_T_RC_time
            delays.append(channel.delay)

            # Note: Compensation limits are specified before attenuation, i.e. at AWG output level.
            #       Convert compensation limit to device level.
            info.dc_compensation_min = channel.compensation_limits[0] * info.attenuation
            info.dc_compensation_max = channel.compensation_limits[1] * info.attenuation
            info.dc_compensation = info.dc_compensation_min < 0 and info.dc_compensation_max > 0

        for channel in marker_channels.values():
            delays.append(channel.delay - channel.setup_ns)
            delays.append(channel.delay + channel.hold_ns)

        for channel in digitizer_channels.values():
            delays.append(channel.delay)
            if channel.rf_source is not None:
                rf_source = channel.rf_source
                delays.append(rf_source.delay - rf_source.startup_time_ns)
                delays.append(rf_source.delay + rf_source.prolongation_ns)

        self.max_pre_start_ns = -min(0, *delays)
        self.max_post_end_ns = max(0, *delays)


    def _integrate(self, job):

        if not job.neutralize:
            return

        for iseg,seg in enumerate(job.sequence):
            # fixed sample rate
            sample_rate = 1e9

            for channel_name, channel_info in self.channels.items():
                if iseg == 0:
                    channel_info.integral = 0

                if channel_info.dc_compensation:
                    seg_ch = seg[channel_name]
                    channel_info.integral += seg_ch.integrate(job.index, sample_rate)
                    logger.debug(f'Integral seg:{iseg} {channel_name} integral:{channel_info.integral}')


    def _process_segments(self, job):
        self.segments = []
        segments = self.segments
        t_start = 0
        for seg in job.sequence:
            duration = seg.get_total_time(job.index)
            t_end = t_start+duration
            info = SegmentRenderInfo(t_start, t_end)
            segments.append(info)
            t_start = info.t_end

        # add DC compensation
        compensation_time = self.get_max_compensation_time()
        compensation_time_ns = PulsarConfig.ceil(compensation_time*1e9)
        logger.info(f'DC compensation time: {compensation_time_ns} ns')

        job.upload_info.dc_compensation_duration_ns = compensation_time_ns

        job.playback_time = segments[-1].t_end + compensation_time_ns
        logger.debug(f'Playback time: {job.playback_time} ns')

        if UploadAggregator.verbose:
            for segment in segments:
                logger.info(f'segment: {segment}')

    def get_markers(self, job, marker_channel):
        # Marker on periods can overlap, also across segments.
        # Get all start/stop times and merge them.
        start_stop = []
        segments = self.segments
        for iseg,(seg,seg_render) in enumerate(zip(job.sequence,segments)):
            offset = seg_render.t_start + marker_channel.delay + self.max_pre_start_ns
            seg_ch = seg[marker_channel.name]
            ch_data = seg_ch._get_data_all_at(job.index)

            for pulse in ch_data.my_marker_data:
                start_stop.append((PulsarConfig.floor(offset + pulse.start - marker_channel.setup_ns), +1))
                start_stop.append((PulsarConfig.ceil(offset + pulse.stop + marker_channel.hold_ns), -1))

        # merge markers
        marker_value = 1 << marker_channel.channel_number
        return merge_markers(marker_channel.name, start_stop, marker_value, min_off_ns=20)

    def get_markers_seq(self, job, seq_name):
        marker_names = self.seq_markers.get(seq_name, [])
        if len(marker_names) == 0:
            return []

        markers = []
        for marker_name in marker_names:
            marker_channel = self.marker_channels[marker_name]
            markers += self.get_markers(job, marker_channel)

        s = 0
        last = None
        m = sorted(markers, key=lambda e:e[0])
        seq_markers = []
        for t,value in m:
            s += value
            if last is not None and t == last:
                # multiple markers on same time
                seq_markers[-1] = (t,s)
            else:
                seq_markers.append((t,s))
                last = t

        return seq_markers

    def add_awg_channel(self, job, channel_name):
        segments = self.segments
        channel_info = self.channels[channel_name]

        t_offset = PulsarConfig.align(self.max_pre_start_ns + channel_info.delay_ns)

        if PulsarUploader.resolution_1ns:
            seq = Voltage1nsSequenceBuilder(channel_name, self.program[channel_name],
                                            rc_time=channel_info.bias_T_RC_time)
        else:
            seq = VoltageSequenceBuilder(channel_name, self.program[channel_name],
                                         rc_time=channel_info.bias_T_RC_time)
        seq.set_time_offset(t_offset)
        scaling = 1/(channel_info.attenuation * seq.max_output_voltage*1000)

        markers = self.get_markers_seq(job, channel_name)
        seq.add_markers(markers)

        for iseg,(seg,seg_render) in enumerate(zip(job.sequence,segments)):
            seg_start = seg_render.t_start
            seg_ch = seg[channel_name]
            data = seg_ch._get_data_all_at(job.index)
            entries = data.get_data_elements(break_ramps=True)
            for e in entries:
                # NOTE: alignment is done in VoltageSequenceBuilder
                if isinstance(e, OffsetRamp):
                    t = e.start + seg_start
                    t_end = e.stop + seg_start
                    v_start = scaling * e.v_start
                    v_stop = scaling * e.v_stop
                    seq.ramp(t, t_end, v_start, v_stop)
                elif isinstance(e, IQ_data_single):
                    t = e.start + seg_start
                    t_end = e.stop + seg_start
                    wave_duration = iround(e.stop) - iround(e.start) # 1 ns resolution
                    amod, phmod = get_modulation(e.envelope, wave_duration)
                    if e.coherent_pulsing:
                        phase = e.phase_offset + 2*np.pi*e.frequency*t*1e-9
                    else:
                        phase = e.phase_offset
                    sinewave = SineWaveform(wave_duration, e.frequency, phase, amod, phmod)
                    seq.add_sin(t, t_end, e.amplitude*scaling, sinewave)
                elif isinstance(e, PhaseShift):
                    raise Exception('Phase shift not supported for AWG channel')
                elif isinstance(e, Chirp):
                    raise Exception('Chirp is not supported for AWG channel')
                elif isinstance(e, custom_pulse_element):
                    t = e.start + seg_start
                    t_end = e.stop + seg_start
                    seq.custom_pulse(t, t_end, scaling, e)
                else:
                    raise Exception(f'Unknown pulse element {type(e)}')

        t_end = PulsarConfig.ceil(seg_render.t_end)
        seq.wait_till(t_end)

        compensation_ns = job.upload_info.dc_compensation_duration_ns
        if job.neutralize and compensation_ns > 0 and channel_info.dc_compensation:
            compensation_voltage_mV = -channel_info.integral / compensation_ns * 1e9 /channel_info.attenuation
            job.upload_info.dc_compensation_voltages[channel_name] = compensation_voltage_mV
            seq.add_comment(f'DC compensation: {compensation_voltage_mV:6.2f} mV {compensation_ns} ns')
            logger.debug(f'DC compensation {channel_name}: {compensation_voltage_mV:6.1f} mV {compensation_ns} ns')
            seq.set_offset(t_end, compensation_ns, compensation_voltage_mV/(1000*seq.max_output_voltage))
            seq.set_offset(t_end + compensation_ns, 0, 0.0)

        seq.finalize()

    def add_qubit_channel(self, job, qubit_channel):
        segments = self.segments

        channel_name = qubit_channel.channel_name

        delays = []
        for i in range(2):
            awg_channel_name = qubit_channel.iq_channel.IQ_out_channels[i].awg_channel_name
            delays.append(self.channels[awg_channel_name].delay_ns)
        if delays[0] != delays[1]:
            raise Exception(f'I/Q Channel delays must be equal ({channel_name})')
        t_offset = PulsarConfig.align(self.max_pre_start_ns + delays[0])

        lo_freq = qubit_channel.iq_channel.LO
        nco_freq = get_iq_nco_idle_frequency(job, qubit_channel, job.index)

        seq = IQSequenceBuilder(channel_name, self.program[channel_name],
                                nco_freq,
                                mixer_gain=qubit_channel.correction_gain,
                                mixer_phase_offset=qubit_channel.correction_phase)
        seq.set_time_offset(t_offset)
        attenuation = 1.0 # TODO @@@ check if this is always true..
        scaling = 1/(attenuation * seq.max_output_voltage*1000)

        markers = self.get_markers_seq(job, channel_name)
        seq.add_markers(markers)

        for iseg,(seg,seg_render) in enumerate(zip(job.sequence,segments)):
            seg_start = seg_render.t_start

            seg_ch = seg[channel_name]
            data = seg_ch._get_data_all_at(job.index)

            entries = data.get_data_elements()
            for e in entries:
                if isinstance(e, OffsetRamp):
                    raise Exception('Voltage steps and ramps are not supported for IQ channel')
                elif isinstance(e, IQ_data_single):
                    t_start = e.start + seg_start
                    t_end = e.stop + seg_start
                    wave_duration = iround(e.stop - e.start) # 1 ns resolution for waveform
                    amod, phmod = get_modulation(e.envelope, wave_duration)
                    sinewave = SineWaveform(wave_duration, e.frequency-lo_freq,
                                            e.phase_offset, amod, phmod)
                    seq.pulse(t_start, t_end, e.amplitude*scaling, sinewave)
                elif isinstance(e, PhaseShift):
                    t_start = e.start + seg_start
                    seq.shift_phase(t_start, e.phase_shift)
                elif isinstance(e, Chirp):
                    t_start = e.start + seg_start
                    t_end = e.stop + seg_start
                    chirp = e
                    start_frequency = chirp.start_frequency-lo_freq
                    stop_frequency = chirp.stop_frequency-lo_freq
                    seq.chirp(t_start, t_end, chirp.amplitude*scaling, start_frequency, stop_frequency)
                elif isinstance(e, custom_pulse_element):
                    raise Exception('Custom pulses are not supported for IQ channel')
                else:
                    raise Exception('Unknown pulse element {type(e)}')

        t_end = PulsarConfig.ceil(seg_render.t_end)
        seq.wait_till(t_end)
        # add final markers
        seq.finalize()


    def add_acquisition_channel(self, job, digitizer_channel):
        for name in job.schedule_params:
            if name.startswith('dig_trigger_') or name.startswith('dig_wait'):
                logger.error(f'Trigger with HVI variable is not support for Qblox')

        channel_name = digitizer_channel.name
        t_offset = PulsarConfig.align(self.max_pre_start_ns + digitizer_channel.delay)

        acq_conf = job.acquisition_conf

        if acq_conf.average_repetitions or not job.n_rep:
            n_rep = 1
        else:
            n_rep = job.n_rep

        nco_freq = digitizer_channel.frequency
        seq = AcquisitionSequenceBuilder(channel_name, self.program[channel_name], n_rep,
                                         nco_frequency=nco_freq,
                                         rf_source=digitizer_channel.rf_source)
        seq.set_time_offset(t_offset)
        if digitizer_channel.rf_source is not None:
            seq.offset_rf_ns = PulsarConfig.align(self.max_pre_start_ns + digitizer_channel.rf_source.delay)

        markers = self.get_markers_seq(job, channel_name)
        seq.add_markers(markers)
        if acq_conf.average_repetitions:
            seq.reset_bin_counter(t=0)

        for iseg, (seg, seg_render) in enumerate(zip(job.sequence, self.segments)):
            seg_start = seg_render.t_start
            seg_ch = seg[channel_name]
            acquisition_data = seg_ch._get_data_all_at(job.index).get_data()

            for acquisition in acquisition_data:
                t = PulsarConfig.align(acquisition.start + seg_start)
                t_measure = acquisition.t_measure if acquisition.t_measure is not None else acq_conf.t_measure
                if t_measure is None:
                    raise Exception('measurement time has not been configured')
                # if t_measure = -1, then measure till end of sequence. (time trace feature)
                if t_measure < 0:
                    t_measure = self.segments[-1].t_end - t
                t_measure = PulsarConfig.floor(t_measure)

                if acquisition.n_repeat:
                    seq.repeated_acquire(t, t_measure, acquisition.n_repeat,
                                         PulsarConfig.floor(acquisition.interval))
                    if acq_conf.sample_rate is not None:
                        logger.info(f'Acquisition sample_rate is ignored when n_repeat is set')
                elif acq_conf.sample_rate is not None:
                    n_cycles, trigger_period = _actual_acquisition_points(t_measure, acq_conf.sample_rate)
                    if n_cycles < 1:
                        raise Exception(f'{channel_name} acquisition t_measure ({t_measure}) < 1/sample_rate ({trigger_period})')
                    seq.repeated_acquire(t, trigger_period, n_cycles, trigger_period)
                else:
                    seq.acquire(t, t_measure)

        t_end = PulsarConfig.ceil(seg_render.t_end)
        try:
            seq.wait_till(t_end)
        except:
            raise Exception(f"Acquisition doesn't fit in sequence. Add a wait to extend the sequence.")
        seq.finalize()
        job.acq_data_scaling[channel_name] = seq.get_data_scaling()

    def add_marker_seq(self, job, channel_name):
        seq = SequenceBuilderBase(channel_name, self.program[channel_name])

        markers = self.get_markers_seq(job, channel_name)
        seq.add_markers(markers)
        seq.finalize()

    def build(self, job):
        job.upload_info = JobUploadInfo()
        times = []
        times.append(['start', time.perf_counter()])

        name = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        self.program = self.q1instrument.new_program(name)
        job.program = self.program
        self.program.repetitions = job.n_rep if job.n_rep else 1

        self.program._timeline.disable_update() # @@@ Yuk

        times.append(['init', time.perf_counter()])

        self._integrate(job)

        times.append(['integrate', time.perf_counter()])

        self._process_segments(job)

        times.append(['proc_seg', time.perf_counter()])

        for channel_name in self.awg_voltage_channels:
            self.add_awg_channel(job, channel_name)

        times.append(['awg', time.perf_counter()])

        for qubit_channel in self.qubit_channels.values():
            self.add_qubit_channel(job, qubit_channel)

        times.append(['qubit', time.perf_counter()])

        for dig_channel in self.digitizer_channels.values():
            self.add_acquisition_channel(job, dig_channel)

        times.append(['dig', time.perf_counter()])

        for seq_name in self.marker_sequencers:
            self.add_marker_seq(job, seq_name)

        times.append(['marker', time.perf_counter()])

        self.program._timeline.enable_update() # @@@ Yuk

        times.append(['done', time.perf_counter()])

        # NOTE: compilation is 20...30% faster with listing=False, add_comments=False
        if UploadAggregator.verbose:
            self.program.compile(listing=True, json=True)
        else:
            retry = False
            try:
                self.program.compile(add_comments=False, listing=False, json=False)
            except Exception as ex:
                retry = True
                print(f'Exception {ex} was raised during compilation. Compiling again with comments.')
            if retry:
                # retry with listing and comments.
                self.program.compile(add_comments=True, listing=True, json=True)

        times.append(['compile', time.perf_counter()])

        if UploadAggregator.verbose:
            prev = None
            for step,t in times:
                if prev:
                    duration = (t - prev)*1000
                    logger.debug(f'duration {step:10} {duration:9.3f} ms')
                prev = t

    def get_max_compensation_time(self):
        '''
        generate a DC compensation of the pulse.
        As usuallly we put capacitors in between the AWG and the gate on the sample, you need to correct
        for the fact that the low fequencies are not present in your transfer function.
        This can be done simply by making the total integral of your function 0.

        Args:
            sample_rate (float) : rate at which the AWG runs.
        '''
        if len(self.channels) == 0:
            return 0
        return max(self.get_compensation_time(channel_info) for channel_info in self.channels.values())

    def get_compensation_time(self, channel_info):
        '''
        return the minimal compensation time that is needed.
        Returns:
            compensation_time : minimal duration that is needed for the voltage compensation
        '''
        if not channel_info.dc_compensation:
            return 0

        if channel_info.integral <= 0:
            result = -channel_info.integral / channel_info.dc_compensation_max
        else:
            result = -channel_info.integral / channel_info.dc_compensation_min
        return result


