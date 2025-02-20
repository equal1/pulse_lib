# qcodes has moved the DummyInstrument. Try old and new location
try:
    from qcodes.tests.instrument_mocks import DummyInstrument
except Exception:
    from qcodes.instrument_drivers.mock_instruments import DummyInstrument
