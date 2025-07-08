
from pulse_lib.tests.configurations.test_configuration import context

#%%
import pulse_lib.segments.utility.looping as lp


def test():
    pulse = context.init_pulselib(n_gates=1, n_sensors=1)

    t_pulse = lp.linspace(20, 100, 5, name='t_pulse', axis=0)
    amplitude = 1000.0 / t_pulse

    s = pulse.mk_segment()

    s.wait(100)
    s.P1.add_block(0, t_pulse, amplitude)
    s.wait(100, reset_time=True)
    s.SD1.acquire(0, 100)
    s.wait(100)

    context.plot_segments([s])

    sequence = pulse.mk_sequence([s])
    m_param = sequence.get_measurement_param()
    for t in sequence.t_pulse.values:
        sequence.t_pulse(t)
        context.plot_awgs(sequence, ylim=(-0.100, 0.100))
    ds = context.run('test_1D_divide', sequence, m_param)

    return ds


if __name__ == '__main__':
    ds = test()
