
from pulse_lib.tests.configurations.test_configuration import context


# %%
def test1():
    """Specific test for bug with ramp > 100 ns at multiple of 4 ns followed and constant voltage of 0.0V >= 4 ns.
    """
    pulse = context.init_pulselib(n_gates=3)

    s = pulse.mk_segment(hres=False)

    s.P1.add_ramp_ss(20, 140, 100.0, 0.0)
    # s.P1.add_block(140, 160, 10.0)
    s.P2.add_ramp_ss(20, 200, 100.0, 0.0)
    # s.P2.add_block(200, 220, 10.0)
    s.P3.add_ramp_ss(20, 308, 100.0, 0.0)
    # s.P3.add_block(308, 320, 10.0)
    s.wait(40)
    s.reset_time()

    for i in range(3):
        s[f"P{i+1}"].add_ramp_ss(0+i, 200+i, 100.0, 0.0)

    s.wait(100, reset_time=True)

    for i in range(3):
        s[f"P{i+1}"].add_block(0+i, 2+i, 100.0)
    s.wait(10, reset_time=True)

    sequence = pulse.mk_sequence([s])
    sequence.n_rep = 2

    context.plot_awgs(sequence, xlim=(0, 800), ylim=(-0.01, 0.12))


def test2():
    pulse = context.init_pulselib(n_gates=2)

    s = pulse.mk_segment(hres=False)

    s.P1.wait(10)
    s.P1.reset_time()
    s.P1.add_block(10, 200, 100.0)
    s.P1.add_ramp_ss(200, 340, 100.0, 0.0)
    s.P1.reset_time()

    s.P1.add_ramp_ss(400, 520, 0.0, 100.0)
    s.P1.add_block(520, 700, 100.0)
    s.P1.add_ramp_ss(700, 840, 100.0, 0.0)

    s.P2.wait(20)
    s.P2.reset_time()
    s.P2.add_block(10, 200, 100.0)
    s.P2.add_ramp_ss(200, 340, 100.0, 0.0)
    s.P2.reset_time()

    s.P2.add_ramp_ss(400, 520, 0.0, 100.0)
    s.P2.add_block(520, 700, 100.0)
    s.P2.add_ramp_ss(700, 840, 100.0, 0.0)

    s.wait(200)

    sequence = pulse.mk_sequence([s])
    sequence.n_rep = 2

    context.plot_awgs(sequence, xlim=(0, 1300), ylim=(-0.01, 0.12))


# %%
if __name__ == '__main__':
    test1()
    test2()
