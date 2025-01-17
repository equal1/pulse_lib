from dataclasses import dataclass


@dataclass
class awg_channel:
    name: str
    awg_name: str
    channel_number: int
    amplitude: float | None = None
    delay: float = 0  # ns
    attenuation: float = 1.0
    compensation_limits: tuple[float, float] = (0, 0)
    bias_T_RC_time: float | None = None
    offset: float | None = None  # mV


@dataclass
class marker_channel:
    name: str
    module_name: str  # could be AWG or digitizer
    channel_number: int | tuple[int, int]
    '''
    Keysight: 0 = trigger out channel, 1...4 = analogue channel
    Tektronix: tuple = (channel,marker number), int = analogue channel
    Qblox: 0...3 = marker out.
    '''
    setup_ns: float
    hold_ns: float
    amplitude: float = 1000
    invert: bool = False
    delay: float = 0  # ns
    sequencer_name: str | None = None
    '''
    Qblox only: name of qubit, awg or digitizer channel to use for sequencing
    '''

# NOTES on digitizer configuration options for M3102A FPGA
#  * Input: I/Q demodulated (external demodulation) with pairing in FPGA
#    Output: I/Q, 2 channels
#    use digitizer_channel_iq and optionally set phase and iq_out
#    digitizer mode: NORMAL or AVERAGING
#    measurement_converter applies phase and generates 1 or 2 raw data outputs depending on iq_out
#
#  * Input: I/Q demodulated (external demodulation) with I/Q pairing in FPGA
#    Output: I/Q, 1 channel, real or complex valued output
#    use digitizer_channel optionally set iq_out=True
#    digitizer mode: IQ_INPUT_SHIFTED_IQ_OUT or IQ_INPUT_SHIFTED_I_ONLY
#    set phase in digitizer
#    measurement_converter generates 1 or 2 raw data outputs depending on iq_out
#
#  * Input: modulated signal, I/Q demodulation in FPGA
#    Output: I/Q, 1 channel, real or complex valued output
#    use digitizer_channel optionally set iq_out=True
#    digitizer mode: IQ_DEMODULATION or IQ_DEMOD_I_ONLY
#    set frequency and phase in digitizer
#    measurement_converter generates 1 or 2 raw data outputs depending on iq_out


@dataclass
class resonator_rf_source:
    '''
    RF source for resonator used with digitizer channel.
    The resonator will be driven with the frequency specified for the digitizer
    channel and dependent on the mode can be enabled synchronous with acquisitions.
    '''
    output: str | tuple[str, int] | tuple[str, list[int]]
    '''
    output: one of the following:
        (str) name of marker channel.
        (Tuple[str, int]) name of module and channel number
        (Tuple[str, List[int]]) name of module and channel numbers
    Configuration for Keysight:
        * Marker channel name if digitizer demodulation frequency is None
        * tuple(AWG module name, channel number) if digitizer demodulation frequeny is not None
    Configuration for Tektronix:
        * Marker channel name if digitizer demodulation frequency is None
    Configuration for Qblox:
        * Marker channel name if digitizer demodulation frequency is None (Not yet supported)
        * tuple(QRM module name, list(channel numbers)) if digitizer demodulation frequeny is not None
    '''
    mode: str = 'pulsed'
    '''
    'continuous', 'pulsed', 'shaped'
    '''
    amplitude: float = 0.0
    '''
    amplitude of the RF source in mV.
    '''
    attenuation: float = 1.0
    '''
    Attenuation of the source channel.
    '''
    delay: float = 0.0
    '''
    rf channel delay [ns]. The signal is delayed with specified amount.
    '''
    startup_time_ns: float = 0.0
    '''
    startup time [ns] of the resonator. Amount of time the source is started before acquisition.
    '''
    prolongation_ns: float = 0.0
    '''
    prolongation [ns] of the pulse after acquisition end in pulsed and continuous mode.
    '''


@dataclass
class digitizer_channel:
    '''
    Channel to retrieve the digitizer data from.

    If multiple channel numbers are specified, than the acquisition for these
    channels is performed simultaneously.

    NOTE:
        On Keysight M3102A with FPGA demodulation this channel does not specify
        the physical digitizer input channel, but the data channel number.
        The digitizer can combine two physical inputs (I and Q) in one output buffer.
        It can also demodulate 1 physcial input to multipe output buffers.
    '''
    name: str
    module_name: str
    channel_numbers: list[int]
    '''
    Channel number to *read* the data from.
    For M3102A this is the number of the output buffer of the digitizer.
    '''
    iq_out: bool = False
    '''
    Return I/Q data in complex value. If False the imaginary component will be discarded.
    Note: sequencer.get_measurement_param has the option to convert to I+Q, amplitude+phase,  etc.
    '''
    phase: float = 0.0
    '''
    Phase shift after iq demodulation
    '''
    iq_input: bool = False
    '''
    Input consists of 2 channels, the demodulated I and Q.
    '''
    frequency: float | None = None
    '''
    demodulation frequency.
    '''
    rf_source: resonator_rf_source | None = None
    '''
    Optional rf_source to generate the resonator drive signal.
    '''
    delay: float = 0.0
    '''
    Channel delay in ns.
    '''
    hw_input_channel: int | None = None
    '''
    For M3102A this is the physical input channel of the digitizer.
    '''
    qblox_nco_propagation_delay: int | None = None
    '''
    Optional nco propagation delay for Qblox.
    This is the time between modulation and demodulation.
    Range: 96 to 245 [ns].
    Expected delay is 148 + ~4 ns/m wiring.
    '''

    def __post_init__(self):
        n_ch = len(self.channel_numbers)
        if self.iq_input and n_ch != 2:
            raise Exception(f'Channel {self.name} specified iq_input, but has {n_ch} channels')

    @property
    def channel_number(self):
        ''' Returns channel number if there is only 1 input channel.
        '''
        if len(self.channel_numbers) != 1:
            raise Exception(f'channel {self.name} has more than 1 channel')
        return self.channel_numbers[0]
