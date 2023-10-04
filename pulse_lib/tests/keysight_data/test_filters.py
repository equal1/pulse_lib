
from pulse_lib.tests.configurations.test_configuration import context

#%%
def test1(filter_mode):
    pulse = context.init_pulselib(n_gates=1)
    context.station.AWG1.set_digital_filter_mode(filter_mode)

    s = pulse.mk_segment()

    s.wait(100)
    s.P1.add_block(20, 220, 100.0)

    sequence = pulse.mk_sequence([s])
    sequence.n_rep = 1
    context.add_hw_schedule(sequence)

    context.plot_awgs(sequence, analogue_out=True)

#    return context.run('hres1', sequence)

def test2(filter_mode, t_ramp):
    pulse = context.init_pulselib(n_gates=1)
    context.station.AWG1.set_digital_filter_mode(filter_mode)

    s = pulse.mk_segment()
    p1 = s.P1
    p1.wait(20)
    p1.reset_time()
    p1.add_ramp_ss(0, t_ramp, 0, 100.0)
    p1.add_block(t_ramp, 200, 100.0)
    p1.reset_time()
    p1.add_ramp_ss(0, t_ramp, 100.0, 0.0)

    sequence = pulse.mk_sequence([s])
    sequence.n_rep = 1
    context.add_hw_schedule(sequence)

    context.plot_awgs(sequence, analogue_out=True)

#    return context.run('hres1', sequence)

#%%
if __name__ == '__main__':
    test1(0)
    test1(1)
    test1(3)

    test2(0, 4)
    test2(1, 4)
    test2(3, 4)
