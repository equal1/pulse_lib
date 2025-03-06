import logging
from collections.abc import Sequence
from typing import Any

import numpy as np
from qcodes import MultiParameter

from pulse_lib.acquisition.iq_modes import iq_mode2func


logger = logging.getLogger(__name__)


def fast_scan1D_param(pulse_lib, gate, swing, n_pt, t_step,
                      biasT_corr=False,
                      acquisition_delay_ns=200,
                      line_margin=0,
                      channels=None,
                      channel_map=None,
                      enabled_markers=[],
                      pulse_gates={},
                      n_avg=1,
                      iq_mode='Complex',
                      iq_complex=None,
                      reload_seq=False):
    """
    Creates a parameter to do a 1D fast scan.

    Args:
        pulse_lib : pulse library object, needed to make the sweep.
        gate (str) : gate/gates that you want to sweep.
        swing (double) : swing to apply on the AWG gates. [mV]
        n_pt (int) : number of points to measure
        t_step (double) : time in ns to measure per point. [ns]
        biasT_corr (bool) : correct for biasT by taking data in different order.
        acquisition_delay_ns (float):
                Time in ns between AWG output change and digitizer acquisition start.
        line_margin (int): number of points to add to sweep 1 to mask transition effects due to voltage step.
            The points are added to begin and end for symmetry (bias-T).
        channels List[str]: digitizer channels to read
        channel_map (Dict[str, Tuple(str, Callable[[np.ndarray], np.ndarray])]):
            defines new list of derived channels to display. Dictionary entries name: (channel_name, func).
            E.g. {(ch1-I':(1, np.real), 'ch1-Q':('ch1', np.imag), 'ch3-Amp':('ch3', np.abs),
                   'ch3-Phase':('ch3', np.angle)}
        enabled_markers (List[str]): marker channels to enable during scan
        pulse_gates (Dict[str, float]):
            Gates to pulse during scan with pulse voltage in mV.
            E.g. {'vP1': 10.0, 'vB2': -29.1}
        n_avg (int): number of times to scan and average data.
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
        reload_seq (bool):
            If True the sequence is uploaded for every 1D scan.
            This gives makes the scan a bit slower, but allows to sweep all pulse-lib settings.

    Returns:
        Parameter (QCODES multiparameter) : parameter that can be used as input in a conversional scan function.
    """
    logger.info(f'fast scan 1D: {gate}')

    # set up timing for the scan
    acquisition_delay = max(100, acquisition_delay_ns)
    step_eff = t_step + acquisition_delay

    if t_step < 1000:
        msg = 'Measurement time too short. Minimum is 1000 ns'
        logger.error(msg)
        raise Exception(msg)

    acq_channels, channel_map = _get_channels(pulse_lib, channel_map, channels, iq_mode, iq_complex)

    vp = swing/2
    line_margin = int(line_margin)
    if biasT_corr and line_margin > 0:
        print('Line margin is ignored with biasT_corr on')
        line_margin = 0

    n_ptx = n_pt + 2*line_margin
    vpx = vp * (n_ptx-1)/(n_pt-1)

    # set up sweep voltages (get the right order, to compensate for the biasT).
    voltages_sp = np.linspace(-vp, vp, n_pt)
    voltages_x = np.linspace(-vpx, vpx, n_ptx)
    if biasT_corr:
        m = (n_ptx+1)//2
        voltages = np.zeros(n_ptx)
        voltages[::2] = voltages_x[:m]
        voltages[1::2] = voltages_x[m:][::-1]
    else:
        voltages = voltages_x

    seg = pulse_lib.mk_segment()
    g1 = seg[gate]
    pulse_channels = []
    for ch, v in pulse_gates.items():
        pulse_channels.append((seg[ch], v))

    if not biasT_corr:
        # pre-pulse to condition bias-T
        t_prebias = n_ptx/2 * step_eff
        g1.add_ramp_ss(0, t_prebias, 0, vpx)
        for gp, v in pulse_channels:
            gp.add_block(0, t_prebias, -v)
        seg.reset_time()

    for i, voltage in enumerate(voltages):
        g1.add_block(0, step_eff, voltage)
        if 0 <= i-line_margin < n_pt:
            for acq_ch in acq_channels:
                seg[acq_ch].acquire(acquisition_delay, t_step)

        for gp, v in pulse_channels:
            gp.add_block(0, step_eff, v)
            # compensation for pulse gates
            if biasT_corr:
                gp.add_block(step_eff, 2*step_eff, -v)
        seg.reset_time()

    if not biasT_corr:
        # post-pulse to discharge bias-T
        g1.add_ramp_ss(0, t_prebias, -vpx, 0)
        for gp, v in pulse_channels:
            gp.add_block(0, t_prebias, -v)
        seg.reset_time()

    end_time = seg.total_time[0]
    for marker in enabled_markers:
        marker_ch = seg[marker]
        marker_ch.reset_time(0)
        marker_ch.add_marker(0, end_time)

    # generate the sequence and upload it.
    my_seq = pulse_lib.mk_sequence([seg])
    my_seq.n_rep = n_avg
    # Note: uses hardware averaging with Qblox modules
    my_seq.set_acquisition(t_measure=t_step, channels=acq_channels, average_repetitions=True)

    if not reload_seq:
        logger.info('Upload')
        my_seq.upload()

    parameters = dict(
        gate=gate,
        swing=dict(label="swing", value=swing, unit="mV"),
        n_pt=n_pt,
        t_measure=dict(label="t_measure", value=t_step, unit="ns"),
        biasT_corr=biasT_corr,
        iq_mode=iq_mode,
        acquisition_delay=dict(
            label="acquisition_delay",
            value=acquisition_delay_ns,
            unit="ns"),
        enabled_markers=enabled_markers,
        pulse_gates={
            name: dict(label=name, value=value, unit="mV")
            for name, value in pulse_gates.items()
        },
        line_margin=line_margin,
    )

    return _scan_parameter(pulse_lib, my_seq, t_step,
                           (n_pt, ), (gate, ), (tuple(voltages_sp), ),
                           biasT_corr, channel_map=channel_map,
                           reload_seq=reload_seq,
                           snapshot_extra={"parameters": parameters})


def fast_scan2D_param(pulse_lib, gate1, swing1, n_pt1, gate2, swing2, n_pt2, t_step,
                      biasT_corr=True,
                      acquisition_delay_ns=200,
                      line_margin=0,
                      channels=None,
                      channel_map=None,
                      enabled_markers=[],
                      pulse_gates={},
                      n_avg=1,
                      iq_mode='Complex',
                      iq_complex=None,
                      reload_seq=False,
                      ):
    """
    Creates a parameter to do a 2D fast scan.

    Args:
        pulse_lib : pulse library object, needed to make the sweep.
        gates1 (str) : gate that you want to sweep on x axis.
        swing1 (double) : swing to apply on the AWG gates.
        n_pt1 (int) : number of points to measure (current firmware limits to 1000)
        gate2 (str) : gate that you want to sweep on y axis.
        swing2 (double) : swing to apply on the AWG gates.
        n_pt2 (int) : number of points to measure (current firmware limits to 1000)
        t_step (double) : time in ns to measure per point.
        biasT_corr (bool) : correct for biasT by taking data in different order.
        acquisition_delay_ns (float):
                Time in ns between AWG output change and digitizer acquisition start.
                This also increases the gap between acquisitions.
        line_margin (int): number of points to add to sweep 1 to mask transition effects due to voltage step.
            The points are added to begin and end for symmetry (bias-T).
        channels List[str]: digitizer channels to read
        channel_map (Dict[str, Tuple(str, Callable[[np.ndarray], np.ndarray])]):
            defines new list of derived channels to display. Dictionary entries name: (channel_name, func).
            E.g. {(ch1-I':(1, np.real), 'ch1-Q':('ch1', np.imag), 'ch3-Amp':('ch3', np.abs),
                   'ch3-Phase':('ch3', np.angle)}
        enabled_markers (List[str]): marker channels to enable during scan
        pulse_gates (Dict[str, float]):
            Gates to pulse during scan with pulse voltage in mV.
            E.g. {'vP1': 10.0, 'vB2': -29.1}
        n_avg (int): number of times to scan and average data.
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
        reload_seq (bool):
            If True the sequence is uploaded for every 2D scan.
            This gives makes the scan a bit slower, but allows to sweep all pulse-lib settings.

    Returns:
        Parameter (QCODES multiparameter) : parameter that can be used as input in a conversional scan function.
    """
    logger.info(f'Fast scan 2D: {gate1} {gate2}')

    # set up timing for the scan
    acquisition_delay = max(100, acquisition_delay_ns)
    step_eff = t_step + acquisition_delay

    if t_step < 1000:
        msg = 'Measurement time too short. Minimum is 1000 ns'
        logger.error(msg)
        raise Exception(msg)

    acq_channels, channel_map = _get_channels(pulse_lib, channel_map, channels, iq_mode, iq_complex)

    line_margin = int(line_margin)
    add_pulse_gate_correction = biasT_corr and len(pulse_gates) > 0

    # set up sweep voltages (get the right order, to compenstate for the biasT).
    vp1 = swing1/2
    vp2 = swing2/2

    voltages1_sp = np.linspace(-vp1, vp1, n_pt1)
    voltages2_sp = np.linspace(-vp2, vp2, n_pt2)

    n_ptx = n_pt1 + 2*line_margin
    vpx = vp1 * (n_ptx-1)/(n_pt1-1)

    if biasT_corr:
        m = (n_pt2+1)//2
        voltages2 = np.zeros(n_pt2)
        voltages2[::2] = voltages2_sp[:m]
        voltages2[1::2] = voltages2_sp[m:][::-1]
    else:
        voltages2 = voltages2_sp

    seg = pulse_lib.mk_segment()

    g1 = seg[gate1]
    g2 = seg[gate2]
    pulse_channels = []
    for ch, v in pulse_gates.items():
        pulse_channels.append((seg[ch], v))

    if biasT_corr:
        # prebias: add half line with +vp2
        prebias_pts = (n_ptx)//2
        t_prebias = prebias_pts * step_eff
        # pulse on fast gate to pre-charge bias-T
        g1.add_block(0, t_prebias, vpx*0.35)
        # correct voltage to ensure average == 0.0 (No DC correction pulse needed at end)
        # Note that voltage on g2 ends center of sweep, i.e. (close to) 0.0 V
        total_duration = 2*prebias_pts + n_ptx*n_pt2 * (2 if add_pulse_gate_correction else 1)
        g2.add_block(0, -1, -(prebias_pts * vp2)/total_duration)
        g2.add_block(0, t_prebias, vp2)
        for g, v in pulse_channels:
            g.add_block(0, t_prebias, -v)
        seg.reset_time()

    for v2 in voltages2:

        g1.add_ramp_ss(0, step_eff*n_ptx, -vpx, vpx)
        g2.add_block(0, step_eff*n_ptx, v2)
        for acq_ch in acq_channels:
            seg[acq_ch].acquire(step_eff*line_margin+acquisition_delay, n_repeat=n_pt1, interval=step_eff)
        for g, v in pulse_channels:
            g.add_block(0, step_eff*n_ptx, v)
        seg.reset_time()

        if add_pulse_gate_correction:
            # add compensation pulses of pulse_channels
            # sweep g1 onces more; best effect on bias-T
            # keep g2 on 0
            g1.add_ramp_ss(0, step_eff*n_ptx, -vpx, vpx)
            for g, v in pulse_channels:
                g.add_block(0, step_eff*n_ptx, -v)
            seg.reset_time()

    if biasT_corr:
        # pulses to discharge bias-T
        # Note: g2 is already 0.0 V
        g1.add_block(0, t_prebias, -vpx*0.35)
        for g, v in pulse_channels:
            g.add_block(0, t_prebias, +v)
        seg.reset_time()

    end_time = seg.total_time[0]
    for marker in enabled_markers:
        marker_ch = seg[marker]
        marker_ch.reset_time(0)
        marker_ch.add_marker(0, end_time)

    # generate the sequence and upload it.
    my_seq = pulse_lib.mk_sequence([seg])
    my_seq.n_rep = n_avg
    # Note: uses hardware averaging with Qblox modules
    my_seq.set_acquisition(t_measure=t_step, channels=acq_channels, average_repetitions=True)

    if not reload_seq:
        logger.info('Seq upload')
        my_seq.upload()

    parameters = dict(
        gate1=gate1,
        swing1=dict(label="swing1", value=swing1, unit="mV"),
        n_pt1=n_pt1,
        gate2=gate2,
        swing2=dict(label="swing2", value=swing2, unit="mV"),
        n_pt2=n_pt2,
        t_measure=dict(label="t_measure", value=t_step, unit="ns"),
        biasT_corr=biasT_corr,
        iq_mode=iq_mode,
        acquisition_delay=dict(
            label="acquisition_delay",
            value=acquisition_delay_ns,
            unit="ns"),
        enabled_markers=enabled_markers,
        pulse_gates={
            name: dict(label=name, value=value, unit="mV")
            for name, value in pulse_gates.items()
        },
        line_margin=line_margin,
    )

    return _scan_parameter(pulse_lib, my_seq, t_step,
                           (n_pt2, n_pt1), (gate2, gate1),
                           (tuple(voltages2_sp), (tuple(voltages1_sp),)*n_pt2),
                           biasT_corr, channel_map, reload_seq=reload_seq,
                           snapshot_extra={"parameters": parameters})


def _get_channels(pulse_lib, channel_map, channels, iq_mode, iq_complex):
    if iq_complex is False:
        iq_mode = 'I+Q'
    if channel_map is not None:
        acq_channels = set(v[0] for v in channel_map.values())
        for key, value in channel_map.items():
            if len(value) == 2:
                # add unit
                channel_map[key] = (value[0], value[1], 'mV')
    else:
        dig_channels = pulse_lib.digitizer_channels
        if channels is None:
            acq_channels = list(dig_channels.keys())
        else:
            acq_channels = channels

        channel_map = {}
        for name in acq_channels:
            dig_ch = dig_channels[name]
            if dig_ch.iq_out:
                ch_funcs = iq_mode2func(iq_mode)
                for postfix, func, unit in ch_funcs:
                    channel_map[name+postfix] = (name, func, unit)
            else:
                channel_map[name] = (name, None, 'mV')

    return acq_channels, channel_map


class _scan_parameter(MultiParameter):
    """
    generator for the parameter f
    """

    def __init__(self, pulse_lib, my_seq, t_measure, shape, names, setpoint,
                 biasT_corr, channel_map, reload_seq, snapshot_extra):
        """
        args:
            pulse_lib (pulselib): pulse library object
            my_seq (sequencer) : sequence of the 1D scan
            t_measure (int) : time to measure per step
            shape (tuple<int>): expected output shape
            names (tuple<str>): name of the gate(s) that are measured.
            setpoint (tuple<np.ndarray>): array witht the setpoints of the input data
            biasT_corr (bool): bias T correction or not -- if enabled -- automatic reshaping of the data.
            channel_map (Dict[str, Tuple(str, Callable[[np.ndarray], np.ndarray])]):
                defines new list of derived channels to display. Dictionary entries name: (channel_name, func).
                E.g. {(ch1-I':(1, np.real), 'ch1-Q':('ch1', np.imag), 'ch3-Amp':('ch3', np.abs),
                       'ch3-Phase':('ch3', np.angle)}
            reload_seq (bool):
                If True the sequence is uploaded for every scan.
                This gives makes the scan a bit slower, but allows to sweep all pulse-lib settings.
            snapshot_extra (dict<str, any>): snapshot
        """
        self.my_seq = my_seq
        self.pulse_lib = pulse_lib
        self.t_measure = t_measure
        self.n_rep = np.prod(shape)
        self.channel_map = channel_map
        self.channel_names = tuple(self.channel_map.keys())
        self.biasT_corr = biasT_corr
        self.shape = shape
        self.reload_seq = reload_seq
        units = tuple(unit for _, _, unit in channel_map.values())
        n_out_ch = len(self.channel_names)

        channel_map_snapshot = {}
        for name, mapping in channel_map.items():
            channel_map_snapshot[name] = {
                "channel": mapping[0],
                "func": getattr(mapping[1], "__name__", str(mapping[1])),
                "unit": mapping[2],
            }
        snapshot_extra["parameters"]["channel_map"] = channel_map_snapshot
        self._snapshot_extra = snapshot_extra

        super().__init__(
            name='fastScan',
            names=self.channel_names,
            shapes=tuple([shape]*n_out_ch),
            labels=self.channel_names,
            units=units,
            setpoints=tuple([setpoint]*n_out_ch),
            setpoint_names=tuple([names]*n_out_ch),
            setpoint_labels=tuple([names]*n_out_ch),
            setpoint_units=(("mV",)*len(names),)*n_out_ch,
            docstring='Scan parameter for digitizer')

    def get_raw(self):

        if self.reload_seq:
            logger.info('Seq upload')
            self.my_seq.upload()
            self.my_seq.play()
        else:
            # play sequence
            self.my_seq.play(release=False)
        raw_dict = self.my_seq.get_channel_data()

        # get the data
        data = []
        for ch, func, _ in self.channel_map.values():
            # channel data already is in mV
            ch_data = raw_dict[ch]
            if func is not None:
                data.append(func(ch_data))
            else:
                data.append(ch_data)

        # make sure that data is put in the right order.
        data_out = [np.zeros(self.shape, dtype=d.dtype) for d in data]

        for i in range(len(data)):
            d = data[i]
            ch_data = d.reshape(self.shape)
            if self.biasT_corr:
                data_out[i][:len(ch_data[::2])] = ch_data[::2]
                data_out[i][len(ch_data[::2]):] = ch_data[1::2][::-1]
            else:
                data_out[i] = ch_data

        return tuple(data_out)

    def snapshot_base(self,
                      update: bool | None = True,
                      params_to_skip_update: Sequence[str] | None = None
                      ) -> dict[Any, Any]:
        snapshot = super().snapshot_base(update, params_to_skip_update)
        snapshot.update(self._snapshot_extra)
        return snapshot

    def stop(self):
        if self.my_seq is not None and self.pulse_lib is not None:
            logger.info('stop: release memory')
            # remove pulse sequence from the AWG's memory, unload schedule and free memory.
            self.my_seq.close()
            self.my_seq = None
            self.pulse_lib = None

    def __del__(self):
        if self.my_seq is not None and self.pulse_lib is not None:
            logger.debug('Automatic cleanup in __del__(); Calling stop()')
            self.stop()
