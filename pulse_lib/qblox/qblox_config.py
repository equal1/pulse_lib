class QbloxConfig:
    """
    Global configuration of qblox pulse generation.
    """

    low_pass_filter_enabled: bool = False
    """
    Enables low pass filtering on acquisitions
    with integration time <= 16_000 ns.
    """
