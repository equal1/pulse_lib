from dataclasses import dataclass


@dataclass
class awg_slave:
    awg_name: str
    marker_name: str
    sync_latency: float | None = None
