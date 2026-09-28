from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any

def now_iso(): return datetime.now(timezone.utc).isoformat()

@dataclass
class ECUData:
    ecu_id: str
    ecu_name: str
    status: str = "ONLINE"
    last_update: str = field(default_factory=now_iso)
    parameters: dict[str, Any] = field(default_factory=dict)

@dataclass
class CANFrame:
    message_id: str
    source_ecu: str
    destination: str
    priority: int
    timestamp: str
    payload: dict[str, Any]
    sequence_counter: int
    auth_tag: str = ""
    authentication_status: str = "PENDING"
    frame_size: int = 64

@dataclass
class EthernetPacket:
    packet_id: str
    source: str
    destination: str
    original_can_id: str
    traffic_class: str
    priority: int
    payload: dict[str, Any]
    created_timestamp: float
    gateway_timestamp: float
    size_bytes: int
    security_status: str
    tsn_enqueue_timestamp: float = 0
    tsn_dequeue_timestamp: float = 0
    receive_timestamp: float = 0
    queue_wait_ms: float = 0
    transmission_time_ms: float = 0
    macsec_nonce: str = ""
    macsec_ciphertext: str = ""
    macsec_tag: str = ""
