import numpy as np
from functools import cache


@cache
def low_pass_window(n: int):
    """ Creates a window with incorporated low pass filter.

    Args:
        n: length of window.

    With n=200 all frequencies above 95 MHz are attenuated with > 81 dB.
    With n=1000 they are attenuated with > 95 dB.
    With n=2000 they are attenuated with > 101 dB, i.e. < 1/100_000 of original amplitude.

    Notes:
        Maximum length for Qblox acquisition weight is 16384 samples.
        This limitation is not enforced here, because this is only
        the implementation of a window and it doesn't know about Qblox QRM.
        A normal boxcar window with length 16000 (and sample rate 1 GSa/s)
        already attenuated frequencies above 100 MHz with 74 dB, i.e.
        1/5000 of input amplitude.
    """
    ramp = [
        0.00458420, 0.01575104, 0.03271758, 0.05871736, 0.09609971,
        0.14609971, 0.20871736, 0.28271758, 0.36575104, 0.45458420,
        0.54541580, 0.63424896, 0.71728242, 0.79128264, 0.85390029,
        0.90390029, 0.94128264, 0.96728242, 0.98424896, 0.99541580,
        ]
    return np.concatenate([ramp, np.ones(n-40), ramp[::-1]])

# %%


if __name__ == "__main__":
    import matplotlib.pyplot as pt
    from numpy.fft import fft

    def plot(w):
        N = 10_000
        fs = 1000  # MHz
        # t = np.arange(N)/fs  # us
        f = np.arange(0, N//2+1)*fs/N  # MHz
        x = np.zeros(N)
        x[0: len(w)] = w / np.sum(w)

        s = fft(x)
        amplitude = np.abs(s)[0: N//2+1]
        pt.plot(f, 20*np.log10(amplitude+1e-20))
        pt.plot(f, 20*np.log10(1000/(f*len(w))/(np.pi)+1e-20))

    w = low_pass_window(1000)

    pt.figure()
    pt.plot(w)

    pt.figure()
    plot(w)
    pt.ylim(-120, 5)
    pt.grid(True)
