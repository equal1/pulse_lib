
from pulse_lib.tests.configurations.test_configuration import context
import pulse_lib.segments.utility.looping as lp


# %%

# Note: hres = True is not yet supported
hres = False


def test1():
    pulse = context.init_pulselib(n_gates=2, n_sensors=2, rf_sources=True)

    segments = []

    s = pulse.mk_segment(hres=hres)
    segments.append(s)

    s.wait(0.2, reset_time=True)

    s.P1.add_sin(50, 1050, 1000, 1.0e6)

    s.P2.add_block(20, 1100, 100)
    s.P2.add_sin(50, 1050, 1000, 1.0e6)

    s.wait(100)

    sequence = pulse.mk_sequence(segments)
    sequence.n_rep = 1

    context.plot_awgs(sequence, xlim=(0, 1100), analogue_out=True)


def test2():
    pulse = context.init_pulselib(n_gates=2, n_sensors=2, rf_sources=True)

    segments = []

    s = pulse.mk_segment(hres=hres)
    segments.append(s)

    s.P1.add_sin(50, 1050, 100, 1.0e6)
    s.P1.add_ramp_ss(20, 1100, 100, 200)
    s.P2.add_ramp_ss(20, 1100, 100, 200)

    s.wait(100)

    sequence = pulse.mk_sequence(segments)
    sequence.n_rep = 1

    context.plot_awgs(sequence)


def test3():
    pulse = context.init_pulselib(n_gates=2, n_sensors=2, rf_sources=True)

    segments = []

    s = pulse.mk_segment(hres=hres)
    segments.append(s)

    s.P1.add_sin(50, 1050, 100, 1.0e6)
    s.P1.add_ramp_ss(20, 320, 100, 150)
    s.P1.add_ramp_ss(320, 1100, 150, 100)
    s.P2.add_ramp_ss(20, 320, 100, 150)
    s.P2.add_ramp_ss(320, 1100, 150, 100)

    s.wait(100)

    sequence = pulse.mk_sequence(segments)
    sequence.n_rep = 1

    context.plot_awgs(sequence)


def test4():
    pulse = context.init_pulselib(n_gates=2, n_sensors=2, rf_sources=True)

    segments = []

    s = pulse.mk_segment(hres=hres)
    segments.append(s)

    s.P1.add_sin(40, 2041, 100, 0.5e6)
    s.P1.add_sin(40, 2041, 50, 1.0e6)
    s.P1.add_ramp_ss(20, 2200, 10, 10)

    s.wait(100, reset_time=True)
    s.SD1.acquire(0, 100, "m1", wait=True)

    sequence = pulse.mk_sequence(segments)
    sequence.n_rep = None

    context.plot_awgs(sequence)
    # m_param = sequence.get_measurement_param()
    # return context.run("shuttle", sequence, m_param)


def test5():
    pulse = context.init_pulselib(n_gates=2, n_sensors=2, rf_sources=True)

    segments = []

    s = pulse.mk_segment(hres=hres)
    segments.append(s)

    f = lp.linspace(0.025e6, 0.010e6, 16, name="frequency", axis=0)

    s.wait(20, reset_time=True)
    t_pulse = 2.75/f*1e9
    s.P1.add_sin(0, t_pulse, 100, f)
    s.reset_time()
    s.P1.add_ramp_ss(0, 300, 100.0, 0.0)
    s.wait(10, reset_time=True)
    s.P1.add_ramp_ss(0, 300, 0.0, 100.0)
    s.reset_time()
    s.P1.add_sin(0, t_pulse, 100, -f)

    s.reset_time()
    s.P2.add_block(0, 100, 50)
    s.wait(100, reset_time=True)
    s.SD1.acquire(0, 100, "m1", wait=True)
    s.wait(200, reset_time=True)

    sequence = pulse.mk_sequence(segments)
    sequence.n_rep = None
    m_param = sequence.get_measurement_param()
    # context.plot_awgs(sequence)
    return context.run("shuttle", sequence, m_param)


# %%

if __name__ == '__main__':
    from pulse_lib.qblox import QbloxConfig
    from pulse_lib.qblox.pulsar_sequencers import SequenceBuilderBase
    QbloxConfig.sine_interpolation_step = 40
    SequenceBuilderBase.verbose = True
    QbloxConfig.double_path_encoding = False

    test1()
    test2()
    test3()
    test4()
    test5()
