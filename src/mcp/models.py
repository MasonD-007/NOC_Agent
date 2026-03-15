from dataclasses import dataclass


@dataclass
class LogEvent:
    timestamp: str
    source_ip: str
    event_type: str
    severity: str
    raw_message: str
