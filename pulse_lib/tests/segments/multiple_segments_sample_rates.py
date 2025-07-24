
from pulse_lib.tests.configurations.test_configuration import context


# %%

# test multiple segments with different sample rates
# check "elimination" of empty segments


def test_multiple():
    pulse = context.init_pulselib(n_gates=2, n_qubits=1, n_sensors=1, n_markers=1)
    f_q1 = pulse.qubit_channels['q1'].resonance_frequency

    t_measure = 1000

    s = pulse.mk_segment('seg1')
    s1 = s

    s.P1.add_ramp_ss(0, 1000, 0, 200)
    s.P1.add_block(1000, 2000, 200)
    s.P1.add_ramp_ss(2000, 3000, 200, 100)
    s.P1.add_block(2000, -1, 100)
    s.q1.add_MW_pulse(10, 250, 150.0, f_q1)
    s.wait(300, reset_time=True)
    s.SD1.acquire(0, t_measure, 'm1', threshold=0.0015, zero_on_high=True, wait=True)
    s.M1.add_marker(0, 800)

    s_wait = pulse.mk_segment(sample_rate=1e8)
    s_wait.wait(1e5, reset_time=True)

    s2 = pulse.mk_segment()
    s = s2

    s2.q1.add_MW_pulse(10, 250, 150.0, f_q1)
    s2.P1.add_block(500, 1000, 100)
    s2.wait(1000, reset_time=True)

    sequence = pulse.mk_sequence([s1, s_wait, s2])
    sequence.n_rep = None

    context.plot_awgs(sequence, ylim=(-0.250, 0.250))

    m_param = sequence.get_measurement_param()
    return context.run('multiple_segments', sequence, m_param)


def test_empty():
    pulse = context.init_pulselib(n_gates=2, n_qubits=2, n_sensors=2, n_markers=1)
    f_q1 = pulse.qubit_channels['q1'].resonance_frequency

    t_measure = 500

    s = pulse.mk_segment('seg1')
    s1 = s

    s.P1.add_ramp_ss(0, 1000, 0, 200)
    s.P1.add_block(1000, 2000, 200)
    s.P1.add_ramp_ss(2000, 3000, 200, 100)
    s.P1.add_block(2000, -1, 100)
    s.q1.add_MW_pulse(10, 250, 150.0, f_q1)
    s.wait(300, reset_time=True)
    s.SD1.acquire(0, t_measure, 'm1', threshold=0.0015, zero_on_high=True, wait=True)
    s.M1.add_marker(0, 800)

    s_wait1 = pulse.mk_segment(sample_rate=2e8)
    s_wait1.wait(1e5, reset_time=True)
    s_empty = pulse.mk_segment()
    s_wait2 = pulse.mk_segment(sample_rate=2e8)
    s_wait2.wait(1e5, reset_time=True)

    s2 = pulse.mk_segment()
    s = s2

    s2.q1.add_MW_pulse(10, 250, 150.0, f_q1)
    s2.P1.add_block(500, 1000, 100)
    s2.wait(1000, reset_time=True)

    sequence = pulse.mk_sequence([s1, s_wait1, s_empty, s_wait2, s2])
    sequence.n_rep = None

    context.plot_awgs(sequence, ylim=(-0.250, 0.250))

    m_param = sequence.get_measurement_param()
    return context.run('multiple_segments_empty', sequence, m_param)


# %%
if __name__ == '__main__':
    from pulse_lib.keysight.M3202A_uploader import UploadAggregator as UploadAggregator_M3202A
    from pulse_lib.keysight.qs_uploader import UploadAggregator as UploadAggregator_QS

    from qcodes_contrib_drivers.drivers.Keysight.SD_common.memory_manager import MemoryManager

    MemoryManager.memory_sizes = {
            (int(1e4), 400),  # Uploading 4e6 samples takes 0.1s.
            (int(1e5), 400),  # Uploading 4e7 samples takes 0.8s.
            (int(1e6), 16),  # Uploading 1.6e7 samples takes 0.3s.
            (int(1e7), 8),  # Uploading 8e7 samples takes 1.6s.
            (int(5e8), 8)  # Uploading 4e8 samples takes 7.5s.
        }

    UploadAggregator_M3202A.verbose = True
    UploadAggregator_QS.verbose = True

    context.init_coretools()
    ds1 = test_multiple()
    ds2 = test_empty()
