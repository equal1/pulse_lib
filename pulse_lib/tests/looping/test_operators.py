import numpy as np
import pulse_lib.segments.utility.looping as lp


def check_loop(loop1: lp.loop_obj, loop2: lp.loop_obj):
    assert isinstance(loop1, lp.loop_obj)
    assert isinstance(loop2, lp.loop_obj)
    assert loop1.setvals == loop2.setvals
    assert loop1.axis == loop2.axis


loop1 = lp.linspace(1.0, 2.0, 5, "loop1", "a.u.", axis=0)

loop2 = 2 * loop1
check_loop(loop1, loop2)

loop2 = loop1 + 2.0
check_loop(loop1, loop2)

loop2 = 1.0 / loop1
check_loop(loop1, loop2)

loop2 = loop1 - 10
check_loop(loop1, loop2)

loop2 = np.sin(loop1)
check_loop(loop1, loop2)

loop2 = loop1 * loop1[2]
check_loop(loop1, loop2)

loop2 = loop1[2] * loop1
check_loop(loop1, loop2)

loop2 = loop1 / np.float64(2.0)
check_loop(loop1, loop2)

loop2 = np.float64(2.0) / loop1
check_loop(loop1, loop2)
