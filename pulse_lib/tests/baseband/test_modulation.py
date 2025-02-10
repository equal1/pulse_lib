import numpy as np

from pulse_lib.tests.configurations.test_configuration import context


# %%

from pulse_lib.qblox.pulsar_sequencers import PulsarConfig

PulsarConfig.NS_SUB_DIVISION = 10


def conveyor_cosine_modulation(
        t: np.ndarray,
        duration: float,
        amplitude: float,
        start_pos: float,
        stop_pos: float,
        mod_period: float,
        phase: float,
        ) -> np.ndarray:
    """Creates a cosine modulated sine pulse: y = sin(center - d*cos(2*pi*t/period) + phase),
    where d = pi*(stop-start) and center = pi*(start+stop).

    Args:
        t: timestamps of samples relative to pulse start [ns]
        duration: duration of pulse [ns]
        amplitude:  amplitude of pulse [ns]
        start_pos: start position in conveyor expressed in conveyor cycles.
        stop_pos: stopt position in conveyor expressed in conveyor cycles.
        mod_period:
            duration of a full period of the modulation. i.e. time from start_pos to stop_pas and return to start_pos.
        phase: phase of the sin at the start of the conveyor (pos = 0)

    y = amplitude * sin(center - d*cos(2*pi*t/period) + phase)

    Note:
        Max frequency (of sin) is max of -d*sin(2*pi*t/period)*2*pi/period = d*2*pi/period
    """
    center = np.pi*(start_pos + stop_pos)
    d = np.pi*(stop_pos - start_pos)
    return amplitude * np.sin(center - d*np.cos(2*np.pi*t/mod_period) + phase)


def conveyor_cosine_modulation_position(
        t: np.ndarray,
        duration: float,
        amplitude: float,
        start_pos: float,
        stop_pos: float,
        mod_period: float,
        ) -> np.ndarray:
    """Creates a cosine modulated sine pulse: y = sin(center - d*cos(2*pi*t/period) + phase),
    where d = pi*(stop-start) and center = pi*(start+stop).

    Args:
        t: timestamps of samples relative to pulse start [ns]
        duration: duration of pulse [ns]
        amplitude:  amplitude of pulse [ns]
        start_pos: start position in conveyor expressed in conveyor cycles.
        stop_pos: stopt position in conveyor expressed in conveyor cycles.
        mod_period:
            duration of a full period of the modulation. i.e. time from start_pos to stop_pas and return to start_pos.
        phase: phase of the sin at the start of the conveyor (pos = 0)

    y = amplitude * sin(center - d*cos(2*pi*t/period) + phase)

    Note:
        Max frequency (of sin) is max of -d*sin(2*pi*t/period)*2*pi/period = d*2*pi/period
    """
    center = np.pi*(start_pos + stop_pos)
    d = np.pi*(stop_pos - start_pos)
    return amplitude * (center - d*np.cos(2*np.pi*t/mod_period))/(2*np.pi)


def test1(hres=False):
    pulse = context.init_pulselib(n_gates=2, n_sensors=1)
#    context.station.AWG1.set_digital_filter_mode(3)
    period = 100.0
    a = 0.0
    b = 2.0

    s = pulse.mk_segment(hres=hres)

    s.SD1.acquire(0, 100)
    s.P1.add_custom_pulse_v2(0, period/2, 100.0,
                             conveyor_cosine_modulation,
                             phase=0.0, start_pos=a, stop_pos=b, mod_period=period)
    s.P2.add_custom_pulse_v2(0, period/2, 100.0,
                             conveyor_cosine_modulation,
                             phase=0.5*np.pi, start_pos=a, stop_pos=b, mod_period=period)
    s.reset_time()
    s.P1.add_custom_pulse_v2(0, period/2, 100.0,
                             conveyor_cosine_modulation,
                             phase=0.0, start_pos=b, stop_pos=a, mod_period=period)
    s.P2.add_custom_pulse_v2(0, period/2, 100.0,
                             conveyor_cosine_modulation,
                             phase=0.5*np.pi, start_pos=b, stop_pos=a, mod_period=period)
    s.reset_time()
    s.P1.add_custom_pulse_v2(0, period, 100.0,
                             conveyor_cosine_modulation,
                             phase=0.0, start_pos=a, stop_pos=b, mod_period=period)
    s.P2.add_custom_pulse_v2(0, period, 100.0,
                             conveyor_cosine_modulation,
                             phase=0.5*np.pi, start_pos=a, stop_pos=b, mod_period=period)
    s.wait(20)

    s.plot()

    sequence = pulse.mk_sequence([s])
    sequence.n_rep = None
    m_param = sequence.get_measurement_param()

    context.plot_awgs(sequence, ylim=(-0.100, 0.100), xlim=(0, 200))

    return context.run('cos_modulation', sequence, m_param)


def test2(hres=False, t_wait=0.0):
    pulse = context.init_pulselib(n_gates=2, n_sensors=1)
#    context.station.AWG1.set_digital_filter_mode(3)
    period = 20.0
    a = 0.0
    b = 1.0

    s = pulse.mk_segment(hres=hres)

    s.SD1.acquire(0, 40)
    s.P2.wait(t_wait)
    s.P2.reset_time()
    s.P1.add_custom_pulse_v2(0, period/2, 100.0,
                             conveyor_cosine_modulation,
                             phase=0.0, start_pos=a, stop_pos=b, mod_period=period)
    s.P2.add_custom_pulse_v2(0, period/2, 100.0,
                             conveyor_cosine_modulation,
                             phase=0.5*np.pi, start_pos=a, stop_pos=b, mod_period=period)
    s.P1.reset_time()
    s.P2.reset_time()
    s.P1.add_block(0, 10, 100.0)
    s.P2.add_block(0, 10, 100.0)
    s.P1.reset_time()
    s.P2.reset_time()
    s.P1.add_custom_pulse_v2(0, period/2, 100.0,
                             conveyor_cosine_modulation,
                             phase=0.0, start_pos=b, stop_pos=a, mod_period=period)
    s.P2.add_custom_pulse_v2(0, period/2, 100.0,
                             conveyor_cosine_modulation,
                             phase=0.5*np.pi, start_pos=b, stop_pos=a, mod_period=period)
    s.P1.reset_time()
    s.P2.reset_time()
    s.P1.add_custom_pulse_v2(0, period, 100.0,
                             conveyor_cosine_modulation,
                             phase=0.0, start_pos=a, stop_pos=b, mod_period=period)
    s.P2.add_custom_pulse_v2(0, period, 100.0,
                             conveyor_cosine_modulation,
                             phase=0.5*np.pi, start_pos=a, stop_pos=b, mod_period=period)
    s.wait(50)

    sequence = pulse.mk_sequence([s])
    sequence.n_rep = None
    m_param = sequence.get_measurement_param()

    context.plot_awgs(sequence, ylim=(-0.100, 0.100), xlim=(0, 100),
                      # analogue_out=True
                      )

    return context.run('cos_modulation2', sequence, m_param)


def test3(hres=False, t_wait=0.0):
    pulse = context.init_pulselib(n_gates=3, n_sensors=1)
#    context.station.AWG1.set_digital_filter_mode(3)
    period = 40.0
    a = 0.0
    b = 0.5
    shake_period = 10.0

    s = pulse.mk_segment(hres=hres)

    s.SD1.acquire(0, 40)
    s.wait(4+t_wait, reset_time=True)
    s.P1.add_custom_pulse_v2(0, period/2, 100.0,
                             conveyor_cosine_modulation,
                             phase=0.0, start_pos=a, stop_pos=b, mod_period=period)
    s.P2.add_custom_pulse_v2(0, period/2, 100.0,
                             conveyor_cosine_modulation,
                             phase=0.5*np.pi, start_pos=a, stop_pos=b, mod_period=period)
    s.P3.add_custom_pulse_v2(0, period/2, 100.0,
                             conveyor_cosine_modulation_position,
                             start_pos=a, stop_pos=b, mod_period=period)
    s.reset_time()
    s.P1.add_custom_pulse_v2(0, 2*shake_period, 100.0,
                             conveyor_cosine_modulation,
                             phase=0.0, start_pos=b, stop_pos=b-0.1, mod_period=shake_period)
    s.P2.add_custom_pulse_v2(0, 2*shake_period, 100.0,
                             conveyor_cosine_modulation,
                             phase=0.5*np.pi, start_pos=b, stop_pos=b-0.1, mod_period=shake_period)
    s.P3.add_custom_pulse_v2(0, 2*shake_period, 100.0,
                             conveyor_cosine_modulation_position,
                             start_pos=b, stop_pos=b-0.1, mod_period=shake_period)
    s.reset_time()
    s.P1.add_custom_pulse_v2(0, period/2, 100.0,
                             conveyor_cosine_modulation,
                             phase=0.0, start_pos=b, stop_pos=a, mod_period=period)
    s.P2.add_custom_pulse_v2(0, period/2, 100.0,
                             conveyor_cosine_modulation,
                             phase=0.5*np.pi, start_pos=b, stop_pos=a, mod_period=period)
    s.P3.add_custom_pulse_v2(0, period/2, 100.0,
                             conveyor_cosine_modulation_position,
                             start_pos=b, stop_pos=a, mod_period=period)
    s.wait(50)

    sequence = pulse.mk_sequence([s])
    sequence.n_rep = None
    m_param = sequence.get_measurement_param()

    context.plot_awgs(sequence, ylim=(-0.100, 0.100), xlim=(0, 200),
                      # analogue_out=True
                      )

    return context.run('cos_modulation3', sequence, m_param)


# @@@ Maxim: shuttling => X90 gate.
# Qblox: break on 4 ns alignment. Z90 = ~2 ns, mZ90= ~6 ns.
# Set build specific break length.


# %%

if __name__ == "__main__":
    test1()
    test1(hres=True)
    test2(hres=True, t_wait=0.2)
    test2(hres=True, t_wait=0.5)
    test3(hres=True, t_wait=0)
    test3(hres=True, t_wait=0.2)
    test3(hres=True, t_wait=0.5)
