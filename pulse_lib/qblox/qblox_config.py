class QbloxConfig:
    """
    Global configuration of qblox pulse generation.
    """

    low_pass_filter_enabled: bool = False
    """
    Enables low pass filtering on acquisitions
    with integration time <= 16_000 ns.
    """

    output_dir: str | None = None
    """
    Path to store q1pulse programs.
    """

    store_programs: bool = False
    """
    If True stores the programs before uploading and executing on hardware.
    """

    dry_run: bool = False
    """
    If True the program will only be compiled, but not executed on the hardware.
    The returned data contain random values.
    Use dry_run=True in combination with store_programs=True to view the
    simulated output of the Qblox modules without using the hardware.
    """

    iq_waveform_per_qubit_pulse: bool = False
    """
    If True generates an IQ waveform pair for every qubit pulse where the phase
    and amplitude are encoded in the waveforms.
    AWG gain will be fixed on 1.0 for I and Q.
    """

    sine_interpolation_step: int | None = None
    """
    Step size for interpolation of sine waves < 1 MHz.

    Recommended value is 40 ns: interpolation error -45 dB @ 1 MHz; max 200 us sine output.
    Minimum value is 16 ns: interpolation error -60 dB @ 1 MHz; max 80 us sine output.
    A value of 100 ns gives an interpolation error -29 dB @ 1 MHz; max 500 us sine output.
    """

    double_path_encoding: bool = False
    """
    TODO
    """
