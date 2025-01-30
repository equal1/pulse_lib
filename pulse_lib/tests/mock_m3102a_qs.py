import logging
from dataclasses import dataclass

from .mock_m3102a import MockM3102A


logger = logging.getLogger(__name__)


@dataclass
class InstructionBase:
    address: int
    wait_after: float
    jump_address: int | None = None


# NOTE: n_cycles > 1 cannot be combined with threshold


@dataclass
class DigitizerInstruction(InstructionBase):
    t_measure: float | None = None
    n_cycles: int = 1
    threshold: float | None = None
    pxi: int | None = None
    measurement_id: int | None = None

    def __str__(self):
        s = f'{self.address:2}: {str(self.t_measure):4}, wait_after {self.wait_after}'
        if self.n_cycles != 1:
            s += f', n_cycles {self.n_cycles}'
        if self.threshold is not None:
            s += f', threshold {self.threshold}'
        if self.pxi is not None:
            s += f', pxi {self.pxi}'
        return s


class SequencerChannel:
    def __init__(self, instrument, number):
        self._instrument = instrument
        self._number = number
        self._schedule = []

    def load_schedule(self, schedule: list[DigitizerInstruction]):
        self._schedule = schedule

    def describe(self):
        print(f'seq {self._number} schedule')
        for inst in self._schedule:
            print(inst)


# mock for M3102A
class MockM3102A_QS(MockM3102A):

    def __init__(self, name, chassis, slot):
        super().__init__(name, chassis, slot)

        self._sequencers = {}
        for i in range(1, 5):
            self._sequencers[i] = SequencerChannel(self, i)

    def get_sequencer(self, number):
        return self._sequencers[number]

    def plot(self):
        # @@@ plot acquisition interval
        pass

    def describe(self):
        for i, seq in self._sequencers.items():
            seq.describe()
