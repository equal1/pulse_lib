
from pulse_lib.tests.configurations.test_configuration import context
import pulse_lib.segments.utility.looping as lp


# %%


def test1(new_order):
    pulse = context.init_pulselib(n_gates=2, n_sensors=2)

    amp1 = lp.linspace(10, 30, 3, "amplitude1", label="Amplitude 1", unit="mV", axis=0)
    amp2 = lp.linspace(10, 40, 4, "amplitude2", label="Amplitude 2", unit="mV", axis=1)
    amp3 = lp.linspace(10, 50, 5, "amplitude3", label="Amplitude 3", unit="mV", axis=2)
    amp4 = lp.linspace(10, 60, 6, "amplitude4", label="Amplitude 4", unit="mV", axis=3)

    s = pulse.mk_segment()
    s['SD1'].acquire(0, 100)
    s['P1'].add_block(0, 1000, amp1)
    s['P2'].add_block(0, 1000, amp2)

    s.wait(1000)

    s['P1'].add_block(0, 1000, amp3)
    s['P2'].add_block(0, 1000, amp4)

    s.wait(1000)

    sequence = pulse.mk_sequence([s])
    sequence.n_rep = 10
    if new_order:
        sequence.reorder_sweep_axis(new_order)

    measurement_param = sequence.get_measurement_param(iq_mode='I', total_selected=False, accept_mask=False)

    print([p.name for p in sequence.params])
    return context.run(f"reordered {new_order}", sequence, measurement_param)


# %%
if __name__ == '__main__':
    ds1 = test1([])
    ds1 = test1([3, 2, 1, 0])
    ds1 = test1([3, 1, 0, 2])
    ds1 = test1([3, ..., 2])
    ds1 = test1(["amplitude2", "amplitude1", ..., "amplitude3", "amplitude4"])
