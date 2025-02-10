
from pulse_lib.tests.configurations.test_configuration import context

# %%
import numpy as np


def hamming_pulse(t: np.ndarray, duration: float, amplitude: float, alpha: float):
    """
    Generates Hamming shaped pulse

    Args:
        t: sample values
        duration: time in ns of the pulse.
        amplitude: amplitude of the pulse
        alpha: alpha coefficient of the Hamming window

    Returns:
        pulse (np.ndarray) : Hamming pulse
    """
    y = np.ones(t.shape)*alpha
    # Note: t[0] is <= 0.0
    y[0] = 2*alpha-1
    y[-1] = 2*alpha-1
    y[1:-1] += (alpha-1) * np.cos(2*np.pi*t[1:-1]/(duration-(t[1]-t[0])))
    return y * amplitude


# %%


def test1():
    pulse = context.init_pulselib(n_gates=1, n_markers=1)

    segments = []

    s = pulse.mk_segment()
    segments.append(s)

    s.M1.add_marker(0, 8)
    s.wait(10, reset_time=True)

    s.P1.add_custom_pulse_v2(15, 75, 100.0, hamming_pulse, alpha=0.55)

    s.wait(10, reset_time=True)

    sequence = pulse.mk_sequence(segments)
    sequence.n_rep = 2
    context.plot_awgs(sequence, ylim=(-0.2, 0.2))


def test2():
    pulse = context.init_pulselib(n_gates=2, n_markers=1)

    segments = []

    s = pulse.mk_segment(hres=True)
    segments.append(s)

    s.M1.add_marker(0, 8)
    s.wait(10, reset_time=True)

    s.P1.add_block(0, 50, 20)
    s.P1.add_custom_pulse_v2(15.0, 35.0, 100.0, hamming_pulse, alpha=0.55)
    s.P2.add_block(0.5, 50.5, 20)
    s.P2.add_custom_pulse_v2(15.5, 35.5, 100.0, hamming_pulse, alpha=0.55)

    s.wait(10, reset_time=True)

    sequence = pulse.mk_sequence(segments)
    sequence.n_rep = 2
    context.plot_awgs(sequence, ylim=(-0.2, 0.2),
                      # analogue_out=True,
                      )


def test3():
    pulse = context.init_pulselib(n_gates=1, n_markers=1)

    segments = []

    s = pulse.mk_segment()
    segments.append(s)

    s.M1.add_marker(0, 8)
    s.wait(10, reset_time=True)

    s.P1.add_ramp_ss(0, 200, -50, 50)
    s.P1.add_custom_pulse_v2(15, 75, 100.0, hamming_pulse, alpha=0.55)

    s.wait(10, reset_time=True)

    sequence = pulse.mk_sequence(segments)
    sequence.n_rep = 2
    context.plot_awgs(sequence, ylim=(-0.2, 0.2))


def test4():
    pulse = context.init_pulselib(n_gates=1, n_markers=1)

    segments = []

    s = pulse.mk_segment()
    segments.append(s)

    s.M1.add_marker(0, 8)
    s.wait(10, reset_time=True)

    s.P1.add_ramp_ss(0, 50, -50, 50)
    s.P1.add_ramp_ss(50, 100, 50, -50)
    s.P1.add_custom_pulse_v2(15, 75, 100.0, hamming_pulse, alpha=0.55)

    s.wait(10, reset_time=True)

    sequence = pulse.mk_sequence(segments)
    sequence.n_rep = 2
    context.plot_awgs(sequence, ylim=(-0.2, 0.2))


def test5():
    pulse = context.init_pulselib(n_gates=1, n_markers=1)

    segments = []

    s = pulse.mk_segment(hres=True)
    segments.append(s)

    s.M1.add_marker(0, 8)
    s.wait(10, reset_time=True)

    s.P1.add_ramp_ss(0, 150, -50, 50)
    s.P1.add_custom_pulse_v2(15.5, 75.5, 100.0, hamming_pulse, alpha=0.5)
    s.P1.add_sin(30, 60, 20.0, 100e6)

    s.wait(10, reset_time=True)
    s.P1.add_sin(30, 60, 20.0, 100e6)

    sequence = pulse.mk_sequence(segments)
    sequence.n_rep = 2
    context.plot_awgs(sequence, ylim=(-0.2, 0.2))


# %%
if __name__ == '__main__':
    ds1 = test1()
    ds2 = test2()
    ds3 = test3()
    ds4 = test4()
    ds5 = test5()

# %%
if False:
    from pulse_lib.tests.utils.last_upload import get_last_upload

    lu = get_last_upload(context.pulse)
