
from pulse_lib.tests.configurations.test_configuration import context


# %%
import pulse_lib.segments.utility.looping as lp


def test1():
    pulse = context.init_pulselib(n_gates=2, n_sensors=2, rf_sources=True)
    t_wait = lp.arange(0, 20, name="t_wait", axis=0)

    s = pulse.mk_segment()

    s.P1.add_block(0, 1000, 100)
    s.SD2.acquire(0, 1000, wait=True)
    s.reset_time()

    # short wait acquire instructions too close?
    s.wait(t_wait, reset_time=True)

    s.P1.add_block(0, 1000, -500)
    s.SD2.acquire(0, 1000, wait=True, threshold=10)
    s.reset_time()

    # short wait rf source instructions too close?
    s.wait(t_wait+340, reset_time=True)

    s.P1.add_block(0, 1000, 100)
    s.SD2.acquire(0, 1000, wait=True, threshold=20)
    s.reset_time()

    sequence = pulse.mk_sequence([s])
    sequence.n_rep = None
    m_param = sequence.get_measurement_param(iq_mode="I")

    return context.run('multiple acquisitions', sequence, m_param, close_sequence=False)


# %%

if __name__ == '__main__':
    from pulse_lib.qblox.pulsar_uploader import UploadAggregator
    UploadAggregator.verbose = True

    ds1 = test1()
