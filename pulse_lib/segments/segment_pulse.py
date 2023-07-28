"""
Class that is used to make DC pulses.
"""
import numpy as np

from pulse_lib.configuration.iq_channels import IQ_out_channel_info
from pulse_lib.segments.segment_base import segment_base
from pulse_lib.segments.utility.data_handling_functions import loop_controller
from pulse_lib.segments.data_classes.data_pulse import pulse_data, custom_pulse_element, pulse_delta
from pulse_lib.segments.data_classes.data_IQ import IQ_data_single
from pulse_lib.segments.segment_IQ import segment_IQ
from dataclasses import dataclass

@dataclass
class IQ_render_info:
    '''
    Rendering information for a single IQ channel and a single qubit segment
    '''
    virtual_channel: segment_IQ
    out_channel: IQ_out_channel_info

class segment_pulse(segment_base):
    '''
    Class defining single segments for one sequence.
    '''
    def __init__(self, name, segment_type='render', hres=False):
        '''
        Args:
            name (str): name of the segment usually the channel name
            segment_type (str) : type of the segment (e.g. 'render' --> to be rendered, 'virtual'--> no not render.)
        '''
        super().__init__(name, pulse_data(hres=hres), segment_type)

    @loop_controller
    def add_block(self,start,stop, amplitude):
        '''
        add a block pulse on top of the existing pulse.
        '''
        self.data_tmp.add_delta(pulse_delta(start + self.data_tmp.start_time,
                                            step=amplitude))
        self.data_tmp.add_delta(pulse_delta(stop + self.data_tmp.start_time if stop != -1 else np.inf,
                                            step=-amplitude))
        return self.data_tmp

    @loop_controller
    def add_ramp(self, start, stop, amplitude, keep_amplitude=False):
        '''
        Makes a linear ramp
        Args:
            start (double) : starting time of the ramp
            stop (double) : stop time of the ramp
            amplitude : total hight of the ramp, starting from the base point
            keep_amplitude : when pulse is done, keep reached amplitude for time infinity
        '''
        raise Exception('add_ramp is deprecated because it caused serious mistakes in pulse sequences !!! '
                        'Use add_ramp_ss.')

    @loop_controller
    def add_ramp_ss(self, start, stop, start_amplitude, stop_amplitude, keep_amplitude=False):
        '''
        Makes a linear ramp (with start and stop amplitude)
        Args:
            start (double) : starting time of the ramp
            stop (double) : stop time of the ramp
            amplitude : total hight of the ramp, starting from the base point
            keep_amplitude : when pulse is done, keep reached amplitude for time infinity
        '''
        return self._add_ramp(start, stop, start_amplitude, stop_amplitude, keep_amplitude)

    def _add_ramp(self, start, stop, start_amplitude, stop_amplitude, keep_amplitude=False):
        '''
        Makes a linear ramp (with start and stop amplitude)
        Args:
            start (double) : starting time of the ramp
            stop (double) : stop time of the ramp
            amplitude : total hight of the ramp, starting from the base point
            keep_amplitude : when pulse is done, keep reached amplitude for time infinity
        '''
        if start != stop:
            ramp = (stop_amplitude-start_amplitude) / (stop-start)
            self.data_tmp.add_delta(pulse_delta(start + self.data_tmp.start_time,
                                                step=start_amplitude,
                                                ramp=ramp))
            if keep_amplitude:
                self.data_tmp.add_delta(pulse_delta(stop + self.data_tmp.start_time,
                                                    ramp=-ramp))
                self.data_tmp.add_delta(pulse_delta(np.inf,
                                                    step=-stop_amplitude))
            else:
                self.data_tmp.add_delta(pulse_delta(stop + self.data_tmp.start_time,
                                                    step=-stop_amplitude,
                                                    ramp=-ramp))
        elif keep_amplitude:
            self.data_tmp.add_delta(pulse_delta(stop + self.data_tmp.start_time,
                                                step=stop_amplitude))
            self.data_tmp.add_delta(pulse_delta(np.inf,
                                                step=-stop_amplitude))

        return self.data_tmp

    @loop_controller
    def wait(self, wait):
        '''
        wait for x ns after the lastest wave element that was programmed.
        Args:
            wait (double) : time in ns to wait
        '''
        self.data_tmp.wait(wait)
        return self.data_tmp

    @loop_controller
    def add_sin(self, start, stop, amp, freq, phase_offset=0):
        '''
        Adds a sine wave to the current segment.
        The pulse does not have a coherent phase with other pulses,
        unlike add_MW_pulse on IQ channels.
        Args:
            start (double) : start time in ns of the pulse
            stop (double) : stop time in ns of the pulse
            amp (double) : amplitude of the pulse
            freq (double) : frequency of the pulse
            phase_offset (double) : offset in phase
        '''
        self.data_tmp.add_MW_data(IQ_data_single(start + self.data_tmp.start_time,
                                                 stop + self.data_tmp.start_time,
                                                 amp, freq,
                                                 phase_offset,
                                                 None, # no envelope
                                                 self.name,
                                                 coherent_pulsing=False))
        return self.data_tmp

    @loop_controller
    def add_custom_pulse(self, start, stop, amplitude, custom_func, **kwargs):
        """
        Adds a custom pulse to this segment.
        Args:
            start (double) : start time in ns of the pulse
            stop (double) : stop time in ns of the pulse
            amplitude (double) : amplitude of the pulse
            custom_func: function to generate the samples for this pulse. It must return a 1D numpy array.
            kwargs: keyword arguments passed into the custom_func

        Example:
            def tukey_pulse(duration, sample_rate, amplitude, alpha):
                n_points = int(round(duration / sample_rate * 1e9))
                return signal.windows.tukey(n_points, alpha) * amplitude

            seg.P1.add_custom_pulse(0, 10, 142.0, tukey_pulse, alpha=0.5)

        """
        pulse_data = custom_pulse_element(start + self.data_tmp.start_time, stop + self.data_tmp.start_time,
                                          amplitude, custom_func, kwargs)
        self.data_tmp.add_custom_pulse_data(pulse_data)
        return self.data_tmp

    def add_reference_channel(self, virtual_channel_reference_info):
        '''
        Add channel reference, this can be done to make by making a pointer to another segment.
        Args:
            virutal_channel_reference_info (dataclass): (defined in pulse_lib.virtual_channel_constructor)
                name (str): human readable name of the virtual gate.
                segment_data (segment_pulse): pointer so the segment corresponsing the the channel name
                multiplication_factor (float64): times how much this segment should be added to the current one.
        '''
        self.reference_channels.append(virtual_channel_reference_info)

    def add_IQ_channel(self, virtual_channel, out_channel):
        '''
        Add a reference to an IQ channel. Same principle as for the virtual one.
        Args:
            virtual_channel (segment_IQ): segment with pulses
            out_channel (IQ_out_channel_info): defines AWG output channel and settings.
        '''
        self.IQ_ref_channels.append(IQ_render_info(virtual_channel, out_channel))

    @loop_controller
    def repeat(self, number):
        '''
        repeat a waveform n times.
        Args:
            number (int) : number of ties to repeat the waveform
        '''
        self.data_tmp.repeat(number)
        return self.data_tmp

    def __copy__(self):
        cpy = segment_pulse(self.name)
        return self._copy(cpy)



if __name__ == '__main__':

    from pulse_lib.segments.segment_HVI_variables import segment_HVI_variables
    test_HVI_marker = segment_HVI_variables("name")

    s = segment_pulse("test", test_HVI_marker)
    from pulse_lib.segments.utility.looping import linspace

    a = tuple()
    b = tuple()
    print(a, b, a+b)
    t2 = linspace(100,500, 20, axis= 0)
    t = linspace(1,50, 10000, name = "test", unit = "test", axis= 0)

    # s.data_tmp = s.data[0]
    s.add_block(20, 50, 20)
    print(s.data[0].total_time)
    s.add_HVI_marker("test", 15)
    # s.reset_time()
    # s.add_block(20, 30, t)
    # s.wait(10)
    # s.plot_segment()
    # plt.show()
    print(s.setpoints)
    # print(s.loops)
    # print(s.units)
    print(test_HVI_marker.data)