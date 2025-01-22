
from pulse_lib.tests.configurations.test_configuration import context


# %%
def test1():
    pulse = context.init_pulselib(n_qubits=1)

    pulse.set_iq_lo('IQ1', 0.0)

    s = pulse.mk_segment()

    s.q1.add_chirp(10, 2000, 1e6, 10e6, 1000)

    context.plot_segments([s])

    sequence = pulse.mk_sequence([s])
    sequence.n_rep = 1
    context.plot_awgs(sequence)

    return None


def test2():
    pulse = context.init_pulselib(n_qubits=1)

    s = pulse.mk_segment()

    s.q1.add_chirp(0, 2000, 2.401e9, 2.410e9, 1000)

    context.plot_segments([s])

    sequence = pulse.mk_sequence([s])
    sequence.n_rep = 1
    context.plot_awgs(sequence)

    return None


def test3():
    pulse = context.init_pulselib(n_qubits=1)

    s = pulse.mk_segment()

    s.q1.add_chirp(0, 2000, 2.399e9, 2.390e9, 1000)

    context.plot_segments([s])

    sequence = pulse.mk_sequence([s])
    sequence.n_rep = 1
    context.plot_awgs(sequence)

    return None


def test4():
    pulse = context.init_pulselib(n_gates=1, n_qubits=1,
                                  # drive_with_plungers=True,
                                  )

    pulse.awg_channels['P1'].attenuation = 0.5

    s = pulse.mk_segment()

    # s.q1.add_chirp(0, 2000, 0.001e9, 0.010e9, 1000)
    s.q1.add_chirp(0, 2000, 2.399e9, 2.390e9, 1000)

    context.plot_segments([s])

    sequence = pulse.mk_sequence([s])
    sequence.n_rep = 1
    sequence.plot(channels=['P1', 'q1'])
    context.plot_awgs(sequence)

    return None

# %%


if __name__ == '__main__':
    ds1 = test1()
    ds2 = test2()
    ds3 = test3()
    ds4 = test4()
