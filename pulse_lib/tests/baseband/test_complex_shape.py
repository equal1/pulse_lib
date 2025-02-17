
from pulse_lib.tests.configurations.test_configuration import context


# %%

def add_lines(seg_ch, lines):
    seg_ch.reset_time()
    for i in range(len(lines)-1):
        x1, y1 = lines[i]
        x2, y2 = lines[i+1]
        seg_ch.add_ramp_ss(x1, x2, y1, y2)
    seg_ch.reset_time()


def test1():
    pulse = context.init_pulselib(n_gates=1)

    s = pulse.mk_segment(hres=False)

    # Dijk, talud
    lines = [
        (0, -140),
        (100, -140),
        (400, 100),
        (500, 100),
        (700, 0),
        ]
    add_lines(s.P1, lines)

    # golfjes
    s.wait(500)
    s.P1.add_sin(0, 500, 10, 20e6)
    s.reset_time()

    # Dijk, smooth
    s.P1.add_sin(0, 400, 100, 1.25e6)
    s.reset_time()
    s.P1.add_ramp_ss(0, 130, 0, -100)
    s.reset_time()
    s.P1.add_block(0, -1, -100)
    s.reset_time()

    # Hollandse huisjes
    s.wait(200, reset_time=True)

    lines = [
        (0, 450),
        (250, 650),
        (350, 650-200/250*100),
        (350, 620),
        (400, 620),
        (400, 650-200/250*150),
        (500, 450),
        ]
    add_lines(s.P1, lines)

    s.wait(80, reset_time=True)

    lines = [
        (0, 600),
        (50, 600),
        (50, 650),
        (100, 650),
        (100, 700),
        (150, 700),
        (150, 750),
        (200, 750),
        (200, 800),
        (250, 800),
        (250, 850),
        (300, 850),
        (300, 800),
        (350, 800),
        (350, 750),
        (400, 750),
        (400, 700),
        (450, 700),
        (450, 650),
        (500, 650),
        (500, 600),
        (550, 600),
        ]

    add_lines(s.P1, lines)

    s.wait(100, reset_time=True)
    s.P1.add_block(0, -1, 100)
    s.P1.add_ramp_ss(0, 140, -100, 0)

    s.wait(200)
    s.reset_time()

    sequence = pulse.mk_sequence([s])
    sequence.n_rep = 2

    context.plot_awgs(sequence,
                      xlim=(0, 3500),
                      # ylim=(-0.01, 0.12),
                      )


# %%
if __name__ == '__main__':
    test1()
