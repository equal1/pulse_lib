from pulse_lib.tests.configurations.test_configuration import context

# %%
from qcodes import Parameter
import numpy as np
from pulse_lib.scan.read_input import read_channels
from core_tools.sweeps.sweeps import do1D
from pulse_lib.configuration.rf_parameters import RfParameters


def test_freq():
    pulse = context.init_pulselib(n_gates=2, n_sensors=2, rf_sources=True)

    rf_frequency = pulse.rf_params['SD2'].frequency
    meas_param = read_channels(pulse, 2_000, channels=['SD2'], iq_mode='amplitude+phase')
    ds = do1D(rf_frequency, 80e6, 120e6, 21, 0.0, meas_param,
              name='frequency_search', reset_param=True).run()

    return ds


class FrequencyWithPhaseCorrection(Parameter):
    def __init__(self, name: str, rf_params: RfParameters, delay_ns: float, phase_offset: float = 0.0):
        self._rf_params = rf_params
        self._delay_ns = delay_ns
        self._phase_offset = phase_offset
        super().__init__(name)

    def set_raw(self, frequency: float):
        frequency_param = self._rf_params.frequency
        phase_param = self._rf_params.phase
        corrected_phase = self._phase_offset-2*np.pi*frequency*self._delay_ns*1e-9
        frequency_param(frequency)
        phase_param(corrected_phase)


def test_freq_with_phase_correction():
    pulse = context.init_pulselib(n_gates=2, n_sensors=2, rf_sources=True)

    rf_delay = 40  # ns
    rf_frequency_with_phase = FrequencyWithPhaseCorrection("frequency", pulse.rf_params["SD2"], rf_delay)

    meas_param = read_channels(pulse, 2_000, channels=['SD2'], iq_mode='amplitude+phase')

    ds = do1D(rf_frequency_with_phase, 80e6, 120e6, 21, 0.0, meas_param,
              name='frequency_search_corrected_phase', reset_param=True).run()

    return ds


def test_ampl():
    pulse = context.init_pulselib(n_gates=2, n_sensors=2, rf_sources=True)

    rf_amplitude = pulse.rf_params['SD2'].source_amplitude
    meas_param = read_channels(pulse, 2_000, channels=['SD2'], iq_mode='I+Q')
    ds = do1D(rf_amplitude, 20.0, 200.0, 10, 0.0, meas_param, name='amplitude_sweep', reset_param=True).run()

    return ds


def test_phase():
    pulse = context.init_pulselib(n_gates=2, n_sensors=2, rf_sources=True)

    rf_phase = pulse.rf_params['SD2'].phase
    meas_param = read_channels(pulse, 2_000, channels=['SD2'], iq_mode='I+Q')
    ds = do1D(rf_phase, 0.0, 2*np.pi, 20, 0.0, meas_param, name='phase_sweep', reset_param=True).run()

    return ds


# %%
if __name__ == '__main__':
    context.init_coretools()
    ds1 = test_freq()
    ds2 = test_ampl()
    ds3 = test_phase()
    ds4 = test_freq_with_phase_correction()
