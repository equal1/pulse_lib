
from pulse_lib.tests.configurations.test_configuration import context


# %%
def test1():
    """Specific test for bug with ramp > 100 ns at multiple of 4 ns followed and constant voltage of 0.0V >= 4 ns.
    """
    pulse = context.init_pulselib(n_gates=2)

    s = pulse.mk_segment(hres=False)

    s.P1.add_block(40, 90, 100.0)
    s.P2.add_block(50, 100, 100.0)
    s.wait(40)
    s.reset_time()
    s.P1.add_block(40, 90, 100.0)
    s.P2.add_block(50, 100, 100.0)

    s.wait(100)

    sequence = pulse.mk_sequence([s])
    sequence.n_rep = 2

    context.plot_awgs(sequence, xlim=(0, 500), ylim=(-0.12, 0.12))


# %%
if __name__ == '__main__':
    test1()
