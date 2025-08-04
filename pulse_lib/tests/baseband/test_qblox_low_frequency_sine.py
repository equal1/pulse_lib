
from pulse_lib.tests.configurations.test_configuration import context


# %%

def test1():
    pulse = context.init_pulselib(n_gates=2, n_sensors=2, rf_sources=True)

    segments = []

    s = pulse.mk_segment()
    segments.append(s)

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

    s = pulse.mk_segment()
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

    s = pulse.mk_segment()
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

    s = pulse.mk_segment()
    segments.append(s)

    s.P1.add_sin(50, 2050, 100, 0.5e6)
    s.P1.add_sin(50, 2050, 50, 1.0e6)
    s.P1.add_ramp_ss(20, 2200, 10, 10)

    s.wait(200)

    sequence = pulse.mk_sequence(segments)
    sequence.n_rep = 1

    context.plot_awgs(sequence)


# %%

if __name__ == '__main__':
    from pulse_lib.qblox import QbloxConfig
    from pulse_lib.qblox.pulsar_sequencers import VoltageSequenceBuilder
    QbloxConfig.sine_interpolation_step = 40
    VoltageSequenceBuilder.verbose = False
    QbloxConfig.double_path_encoding = True

    test1()
    test2()
    test3()
    test4()
