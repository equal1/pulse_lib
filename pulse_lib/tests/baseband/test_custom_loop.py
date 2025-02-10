
from pulse_lib.tests.configurations.test_configuration import context

# %%
from scipy import signal


def tukey_pulse(duration, sample_rate, amplitude, alpha):
    """
    Generates Tukey shaped pulse

    Args:
        duration: time in ns of the pulse.
        sample_rate: sampling rate of the pulse (Sa/s).
        amplitude: amplitude of the pulse
        alpha: alpha coefficient of the Tukey window

    Returns:
        pulse (np.ndarray) : Tukey pulse
    """
    n_points = int(round(duration / sample_rate * 1e9))
    return signal.windows.tukey(n_points, alpha) * amplitude


# %%
import pulse_lib.segments.utility.looping as lp


def test1():
    pulse = context.init_pulselib(n_gates=1, n_markers=1)

    alpha = lp.linspace(0, 1.0, 6, name='alpha', axis=0)

    segments = []

    s = pulse.mk_segment()
    segments.append(s)

    s.M1.add_marker(0, 8)
    s.wait(10, reset_time=True)

    s.P1.add_custom_pulse(15, 75, 100.0, tukey_pulse, alpha=alpha)

    s.wait(10, reset_time=True)

    sequence = pulse.mk_sequence(segments)
    sequence.n_rep = 2

    for alpha in sequence.alpha.values:
        sequence.alpha(alpha)
        context.plot_awgs(sequence, xlim=(0, 100), ylim=(-0.2, 0.2))


# %%
if __name__ == '__main__':
    ds1 = test1()
