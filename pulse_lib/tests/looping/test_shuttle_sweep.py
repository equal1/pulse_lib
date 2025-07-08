
from pulse_lib.tests.configurations.test_configuration import context

# %%
import pulse_lib.segments.utility.looping as lp

upload_seq = False


def test_shuttle_ch(n_pulses=1000):
    pulse = context.init_pulselib(n_gates=7, n_qubits=4, n_sensors=2, n_markers=1,
                                  virtual_gates=True)

    t_wait = lp.linspace(1, 20, 20, axis=0, name='t_wait')

    s = pulse.mk_segment()

    context.segment = s

    for _ in range(n_pulses):
        s.vP1.add_ramp_ss(0, 100, -80, 80)
        s.vP1.wait(t_wait)
        s.vP1.reset_time()

    seq = pulse.mk_sequence([s])
    if upload_seq:
        for t in t_wait:
            seq.t_wait(t)
            seq.upload()
    return seq


def test_shuttle(n_pulses=1000):
    pulse = context.init_pulselib(n_gates=7, n_qubits=4, n_sensors=2, n_markers=1,
                                  virtual_gates=True)

    t_wait = lp.linspace(1, 20, 20, axis=0, name='t_wait')

    s = pulse.mk_segment()

    context.segment = s

    for _ in range(n_pulses):
        s.vP1.add_ramp_ss(0, 100, -80, 80)
        s.vP1.wait(t_wait)
        s.reset_time()  # reset on segment instead of channel

    seq = pulse.mk_sequence([s])
    if upload_seq:
        for t in t_wait:
            seq.t_wait(t)
            seq.upload()
    return seq


def test_shuttle_n(n_pulses=200):
    pulse = context.init_pulselib(n_gates=7, n_qubits=4, n_sensors=2, n_markers=1,
                                  virtual_gates=True)

    # Roughly same total number of pulses (1100 vs 1000), but in 10 shorter sequences.
    n_pulses = lp.linspace(20, n_pulses, 10, axis=1, name='n_pulses')
    t_wait = lp.linspace(1, 20, 20, axis=0, name='t_wait')

    s = pulse.mk_segment()

    context.segment = s

    s.update_dim(n_pulses)
    s.wait(0*t_wait)

    for n, nr in enumerate(n_pulses):
        seg = s[n]
        for _ in range(int(nr)):
            seg.vP1.add_ramp_ss(0, 100, -80, 80)
            seg.vP1.wait(t_wait)
            seg.reset_time()  # reset on segment instead of channel

    seq = pulse.mk_sequence([s])
    if upload_seq:
        for t in t_wait:
            for i in n_pulses:
                seq.t_wait(t)
                seq.n_pulses(i)
                seq.upload()
    return seq


def test_shuttle_n_ch(n_pulses=200):
    pulse = context.init_pulselib(n_gates=7, n_qubits=4, n_sensors=2, n_markers=1,
                                  virtual_gates=True)

    n_pulses = lp.linspace(20, n_pulses, 10, axis=1, name='n_pulses')
    t_wait = lp.linspace(1, 20, 20, axis=0, name='t_wait')

    s = pulse.mk_segment()

    context.segment = s

    s.update_dim(n_pulses)
    s.wait(0*t_wait)

    for n, nr in enumerate(n_pulses):
        seg = s[n]
        for _ in range(int(nr)):
            seg.vP1.add_ramp_ss(0, 100, -80, 80)
            seg.vP1.wait(t_wait)
            seg.vP1.reset_time()

    seq = pulse.mk_sequence([s])
    if upload_seq:
        for t in t_wait:
            for i in n_pulses:
                seq.t_wait(t)
                seq.n_pulses(i)
                seq.upload()
    return seq


# %%

if __name__ == '__main__':
    import time
    context.init_coretools()

    for _ in range(5):
        start = time.perf_counter()
        seq = test_shuttle_ch()
        duration = time.perf_counter() - start
        print(f'duration 0: {duration*1000:5.0f} ms')
        seq.close()
        time.sleep(duration/2)
    time.sleep(2)
    for _ in range(5):
        start = time.perf_counter()
        seq = test_shuttle()
        duration = time.perf_counter() - start
        print(f'duration 1: {duration*1000:5.0f} ms')
        seq.close()
        time.sleep(duration/2)
    time.sleep(2)
    for _ in range(5):
        start = time.perf_counter()
        seq = test_shuttle_n()
        duration = time.perf_counter() - start
        print(f'duration 2: {duration*1000:5.0f} ms')
        seq.close()
        time.sleep(duration/2)
    time.sleep(2)
    for _ in range(5):
        start = time.perf_counter()
        seq = test_shuttle_n_ch()
        duration = time.perf_counter() - start
        print(f'duration 3: {duration*1000:5.0f} ms')
        seq.close()
        time.sleep(duration/2)

# %%
'''
Compile only!

V1.7.33 Python 3.10:
duration 0:   779 ms
duration 0:   580 ms
duration 0:   569 ms
duration 0:   550 ms
duration 0:   527 ms
duration 1:  2028 ms
duration 1:  1754 ms
duration 1:  2100 ms
duration 1:  1596 ms
duration 1:  2040 ms
duration 2:  2593 ms
duration 2:  2523 ms
duration 2:  2529 ms
duration 2:  1995 ms
duration 2:  2513 ms
duration 3:  1475 ms
duration 3:  1462 ms
duration 3:  1455 ms
duration 3:  1421 ms
duration 3:  1701 ms

V1.7.33 Python 3.12:
    (Indeed, 0 is slower. Rest is faster.)
duration 0:   957 ms
duration 0:   845 ms
duration 0:   866 ms
duration 0:   743 ms
duration 0:   773 ms
duration 1:  1580 ms
duration 1:  1555 ms
duration 1:  1466 ms
duration 1:  1763 ms
duration 1:  1533 ms
duration 2:  1963 ms
duration 2:  2128 ms
duration 2:  2032 ms
duration 2:  2216 ms
duration 2:  2018 ms
duration 3:  1247 ms
duration 3:  1246 ms
duration 3:  1338 ms
duration 3:  1341 ms
duration 3:  1294 ms

V1.7.54:
duration 0:   843 ms
duration 0:   719 ms
duration 0:   811 ms
duration 0:   817 ms
duration 0:   839 ms
duration 1:  1391 ms
duration 1:  1661 ms
duration 1:  1725 ms
duration 1:  1521 ms
duration 1:  1635 ms
duration 2:  2030 ms
duration 2:  1792 ms
duration 2:  1827 ms
duration 2:  1882 ms
duration 2:  1850 ms
duration 3:   826 ms
duration 3:  1064 ms
duration 3:   809 ms
duration 3:   962 ms
duration 3:   944 ms

V1.7.55: (should be same as 1.7.54)
duration 0:   986 ms
duration 0:   812 ms
duration 0:   876 ms
duration 0:   852 ms
duration 0:   723 ms
duration 1:  1604 ms
duration 1:  2038 ms
duration 1:  1562 ms
duration 1:  1945 ms
duration 1:  1906 ms
duration 2:  2403 ms
duration 2:  1996 ms
duration 2:  2181 ms
duration 2:  2295 ms
duration 2:  2165 ms
duration 3:  1004 ms
duration 3:   835 ms
duration 3:  1002 ms
duration 3:   959 ms
duration 3:  1093 ms

=================
With Qblox upload:

V1.7.33 Python 3.10:
duration 0: 17310 ms
duration 0: 15030 ms
duration 0: 14845 ms
duration 0: 15748 ms
duration 0: 15508 ms
duration 1: 15577 ms
duration 1: 15865 ms
duration 1: 17307 ms
duration 1: 16780 ms
duration 1: 20527 ms
duration 2: 31171 ms
duration 2: 29705 ms
duration 2: 30363 ms
duration 2: 32350 ms
duration 2: 30689 ms
duration 3: 27934 ms
duration 3: 27757 ms
duration 3: 28559 ms
duration 3: 28971 ms
duration 3: 35491 ms

V1.7.33 Python 3.12:
duration 0: 11530 ms
duration 0: 14099 ms
duration 0: 11990 ms
duration 0: 11539 ms
duration 0: 12998 ms
duration 1: 12507 ms
duration 1: 13040 ms
duration 1: 14156 ms
duration 1: 14752 ms
duration 1: 13901 ms
duration 2: 24789 ms
duration 2: 26536 ms
duration 2: 23789 ms
duration 2: 27625 ms
duration 2: 26939 ms
duration 3: 23312 ms
duration 3: 24351 ms
duration 3: 24533 ms
duration 3: 23496 ms
duration 3: 24580 ms

V1.7.54: (same 1.7.55)
    (Don't know why 0 and 1 got slower...)
duration 0: 20379 ms
duration 0: 17836 ms
duration 0: 20023 ms
duration 0: 17902 ms
duration 0: 19496 ms
duration 1: 21848 ms
duration 1: 19412 ms
duration 1: 18722 ms
duration 1: 19380 ms
duration 1: 22607 ms
duration 2: 23506 ms
duration 2: 21419 ms
duration 2: 21939 ms
duration 2: 22648 ms
duration 2: 22317 ms
duration 3: 19819 ms
duration 3: 20673 ms
duration 3: 19838 ms
duration 3: 22730 ms
duration 3: 22625 ms

'''

'''
V1.6.31:
duration 1:  4897 ms
duration 1:  4715 ms
duration 1:  4611 ms
duration 1:  4799 ms
duration 1:  4846 ms
duration 2:  5929 ms
duration 2:  6019 ms
duration 2:  6105 ms
duration 2:  6070 ms
duration 2:  6035 ms

No cache:
duration 1:  4601 ms
duration 1:  4723 ms
duration 1:  4751 ms
duration 1:  5778 ms
duration 1:  4846 ms
duration 2:  5584 ms
duration 2:  5689 ms
duration 2:  5581 ms
duration 2:  5697 ms
duration 2:  5483 ms

Added lazy reset time:
duration 1:  3617 ms
duration 1:  3529 ms
duration 1:  3762 ms
duration 1:  3649 ms
duration 1:  3644 ms
duration 2:  5813 ms
duration 2:  5771 ms
duration 2:  5620 ms
duration 2:  5776 ms
duration 2:  5791 ms

duration 1:  3694 ms
duration 1:  3628 ms
duration 1:  3714 ms
duration 1:  3726 ms
duration 1:  4018 ms
duration 2:  6346 ms
duration 2:  5906 ms
duration 2:  5870 ms
duration 2:  5730 ms
duration 2:  6212 ms

Added end_time cache:
duration 1:  4269 ms
duration 1:  3399 ms
duration 1:  3594 ms
duration 1:  3534 ms
duration 1:  3330 ms
duration 2:  5496 ms
duration 2:  5462 ms
duration 2:  5558 ms
duration 2:  5472 ms
duration 2:  5428 ms

duration 1:  3411 ms
duration 1:  3364 ms
duration 1:  3474 ms
duration 1:  3432 ms
duration 1:  3469 ms
duration 2:  5560 ms
duration 2:  6079 ms
duration 2:  5089 ms
duration 2:  5364 ms
duration 2:  5416 ms

duration 0:  3651 ms
duration 0:  3377 ms
duration 0:  3281 ms
duration 0:  3391 ms
duration 0:  3325 ms
duration 1:  3837 ms
duration 1:  3468 ms
duration 1:  3485 ms
duration 1:  3547 ms
duration 1:  3699 ms
duration 2:  5275 ms
duration 2:  5624 ms
duration 2:  5650 ms
duration 2:  5425 ms
duration 2:  5534 ms
duration 3:  4102 ms
duration 3:  4202 ms
duration 3:  4371 ms
duration 3:  4166 ms
duration 3:  4237 ms

# improved pulse_data.__mul__:
duration 0:   698 ms
duration 0:   833 ms
duration 0:   697 ms
duration 0:   661 ms
duration 0:   671 ms
duration 1:   892 ms
duration 1:   753 ms
duration 1:   874 ms
duration 1:   743 ms
duration 1:   745 ms
duration 2:  2644 ms
duration 2:  2488 ms
duration 2:  2516 ms
duration 2:  2383 ms
duration 2:  2521 ms
duration 3:  1246 ms
duration 3:  1245 ms
duration 3:  1213 ms
duration 3:  1283 ms
duration 3:  1235 ms

without lazy_reset, with end_times:
duration 0:   742 ms
duration 0:   744 ms
duration 0:   837 ms
duration 0:   709 ms
duration 0:   762 ms
duration 1:  1753 ms
duration 1:  1859 ms
duration 1:  1715 ms
duration 1:  1854 ms
duration 1:  1755 ms
duration 2:  2635 ms
duration 2:  2261 ms
duration 2:  2446 ms
duration 2:  2424 ms
duration 2:  2355 ms
duration 3:  1319 ms
duration 3:  1309 ms
duration 3:  1200 ms
duration 3:  1393 ms
duration 3:  1273 ms

with lazy_reset:
duration 0:   727 ms
duration 0:   790 ms
duration 0:   829 ms
duration 0:   814 ms
duration 0:   677 ms
duration 1:  1778 ms
duration 1:  1843 ms
duration 1:  1872 ms
duration 1:  1811 ms
duration 1:  1706 ms
duration 2:  2471 ms
duration 2:  2403 ms
duration 2:  2358 ms
duration 2:  2479 ms
duration 2:  2451 ms
duration 3:  1275 ms
duration 3:  1263 ms
duration 3:  1302 ms
duration 3:  1294 ms
duration 3:  1398 ms

without end_times, without lazy_reset:
duration 0:   765 ms
duration 0:   734 ms
duration 0:   863 ms
duration 0:   690 ms
duration 0:   786 ms
duration 1:  1871 ms
duration 1:  2068 ms
duration 1:  1769 ms
duration 1:  1930 ms
duration 1:  1841 ms
duration 2:  2443 ms
duration 2:  2505 ms
duration 2:  2607 ms
duration 2:  2454 ms
duration 2:  2702 ms
duration 3:  1259 ms
duration 3:  1379 ms
duration 3:  1272 ms
duration 3:  1292 ms
duration 3:  1306 ms

'''
