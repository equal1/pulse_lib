
from pulse_lib.tests.configurations.test_configuration import context


#%%
def test1(filter_mode):
    pulse = context.init_pulselib(n_gates=1)
    context.station.AWG1.set_digital_filter_mode(filter_mode)

    s = pulse.mk_segment(hres=True)

    s.wait(10)
    s.reset_time()
    s.wait(20)
    s.P1.add_ramp_ss(0, 3, 0, 80)
    s.P1.add_block(3, 15, 80)
    s.P1.add_ramp_ss(15, 18, 80, 0)
    s.reset_time()
    s.P1.add_sin(10, 40, 50, 350e6)

    s.wait(20)
    sequence = pulse.mk_sequence([s])
    sequence.n_rep = None

    context.plot_awgs(sequence, analogue_out=True, ylim=(-0.1,0.100), xlim=(0, 80))


#%%
if __name__ == '__main__':
    ds1 = test1(0)
    ds1 = test1(1)
    ds1 = test1(3)
