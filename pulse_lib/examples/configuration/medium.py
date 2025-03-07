from pulse_lib.base_pulse import pulselib

_backend = 'Qblox'
# _backend = 'Keysight'
# _backend = 'Keysight_QS'

_ch_offset = 0


def init_hardware():
    global _ch_offset

    if _backend == 'Qblox':
        _ch_offset = 0
        from .init_pulsars import qcm0, qrm1
        return [qcm0], [qrm1]
    if _backend == 'Keysight':
        _ch_offset = 1
        from .init_keysight import awg1, awg2, dig1
        return [awg1, awg2], [dig1]
    if _backend == 'Keysight_QS':
        _ch_offset = 1
        from .init_keysight_qs import awg1, dig1
        TODO()
        return [awg1], [dig1]


def init_pulselib(awgs, digitizers, virtual_gates=False, bias_T_rc_time=None):

    pulse = pulselib(_backend)
    pulse.configure_digitizer = True

    for awg in awgs:
        pulse.add_awg(awg)

    for dig in digitizers:
        pulse.add_digitizer(dig)

    awg1 = awgs[0].name
    # define channels
    pulse.define_channel('P1', awg1, 0 + _ch_offset)
    pulse.define_channel('P2', awg1, 1 + _ch_offset)
    pulse.define_channel('P3', awg1, 2 + _ch_offset)
    pulse.define_channel('P4', awg1, 3 + _ch_offset)

    pulse.define_marker('M1', awg1, 0, setup_ns=40, hold_ns=20)

    dig_name = digitizers[0].name if len(digitizers) > 0 else 'Dig1'

    pulse.define_digitizer_channel('SD1', dig_name, 0 + _ch_offset)
    if _backend == 'Qblox':
        # No modulation. Just output a rectangular pulse during acquisition.
        pulse.set_digitizer_rf_source('SD1', (dig_name, 0),
                                      mode='pulsed',
                                      amplitude=500,
                                      startup_time_ns=500,
                                      attenuation=1.0)
    else:
        pulse.set_digitizer_rf_source('SD1', 'M1',
                                      mode='pulsed',
                                      startup_time_ns=500)

    pulse.define_digitizer_channel('SD2', dig_name, 1 + _ch_offset, iq_out=True)
    if _backend == 'Qblox':
        pulse.set_digitizer_frequency('SD2', 100e6)
        pulse.set_digitizer_rf_source('SD2', (dig_name, 1),
                                      mode='pulsed',
                                      amplitude=400,
                                      startup_time_ns=500,
                                      attenuation=1.0)

    # add limits on voltages for DC channel compensation (if no limit is specified, no compensation is performed).
    pulse.add_channel_compensation_limit('P1', (-100, 100))
    pulse.add_channel_compensation_limit('P2', (-50, 50))
    pulse.add_channel_compensation_limit('P3', (-80, 80))

    # pulse.add_channel_attenuation('P1', 0.5)

    if bias_T_rc_time:
        pulse.add_channel_bias_T_compensation('P1', bias_T_rc_time)
        pulse.add_channel_bias_T_compensation('P2', bias_T_rc_time)

    if virtual_gates:
        pulse.add_virtual_matrix(
                name='virtual-gates',
                real_gate_names=['P1', 'P2', 'P3', 'P4'],
                virtual_gate_names=['vP1', 'vP2', 'vP3', 'vP4'],
                matrix=[
                    [1.0, -0.1, -0.01, 0.0],
                    [0.1, 1.0, -0.1, -0.01],
                    [0.01, -0.1, 1.0, -0.1],
                    [0.0, -0.01, -0.1, 1.0],
                    ]
                )

    pulse.finish_init()

    return pulse
