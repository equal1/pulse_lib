
from pulse_lib.tests.configurations.test_configuration import context

# %%
import numpy as np

from pulse_lib.qblox.pulsar_sequencers import VoltageSequenceBuilder
from pulse_lib.qblox.pulsar_uploader import UploadAggregator

UploadAggregator.verbose = True
VoltageSequenceBuilder.verbose = True


def config_backend(pulse):
    if pulse._backend in ['Keysight', 'Keysight_QS']:
        context.station.AWG1.set_digital_filter_mode(3)


def test1(t1, t2=10, t_wait=4, n=10, f=100e6, hres=True):
    """
    Special test for Qblox to see whether many repeated unaligned sines
    still results in a limited number of waveforms and limited
    waveform memory use.
    """

    pulse = context.init_pulselib(n_gates=1)
    config_backend(pulse)

    print("length", n*t2*2+n*t_wait)

    s = pulse.mk_segment(hres=hres)
    P1 = s.P1

    s.wait(t1, reset_time=True)
    for _ in range(n):
        P1.add_sin(0, t2, 1000, f, phase_offset=0)
        P1.reset_time()
        P1.add_sin(0, t2, 1000, -f, phase_offset=t2*f*1e-9*2*np.pi)
        P1.wait(t_wait)
        P1.reset_time()

    s.wait(10)

    sequence = pulse.mk_sequence([s])
    sequence.n_rep = None

    context.plot_awgs(sequence,
                      ylim=(-1.10, 1.10),
                      # xlim=(5, 30),
                      analogue_out=True,
                      # analogue_shift=4.0-t1,
                      # create_figure=False,
                      )


# %%
if __name__ == '__main__':
    for t2 in [5.0, 6.0, 8.0, 11.0]:
        test1(10, t2=t2, f=100e6, n=4)

    for t2 in [5.0, 6.0, 8.0, 11.0]:
        test1(10.5, t2=t2, f=1e9/t2, n=4)

    for t2 in [5.2, 6.2, 8.2, 11.2]:
        test1(10, t2=t2, f=1e9/t2, n=4)

    for t_wait in [0.0, 1.0, 5.0, 5.2, 5.4, 5.6, 5.8, 6.0]:
        test1(10, t2=6.2, t_wait=t_wait, f=200e6, n=6)

    for f in np.linspace(100e6, 350e6, 6):
        test1(10, t2=10.2, t_wait=4.0, f=f, n=6)

    # # pt.figure()
    # for t_wait in [5.0, 5.2, 5.4, 5.6, 5.8, 6.0]:
    #     test1(10, t2=6.0, t_wait=10+t_wait, f=200e6, n=8)

    # pt.figure()
    # for t1 in [5.0, 5.2, 5.4, 5.6, 5.8, 6.0]:
    #     test1(t1, t2=6.0, t_wait=10, f=200e6, n=8)
