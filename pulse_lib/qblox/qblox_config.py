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
