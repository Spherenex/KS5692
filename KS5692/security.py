import hashlib, hmac, json
from dataclasses import asdict

class SecurityManager:
    def __init__(self, key=b"ks5692-educational-key"):
        self.key = key

    def tag(self, frame):
        raw = f"{frame.message_id}|{frame.source_ecu}|{frame.sequence_counter}|{json.dumps(frame.payload, sort_keys=True)}".encode()
        return hmac.new(self.key, raw, hashlib.sha256).hexdigest()[:20]

    def sign(self, frame):
        frame.auth_tag = self.tag(frame); frame.authentication_status = "AUTHENTICATED"; return frame

    def verify(self, frame, last_counters):
        if frame.source_ecu not in {"BMS", "MCU", "VCU", "ADAS", "CCU"}: return False, "Unauthorized source"
        if frame.sequence_counter <= last_counters.get(frame.source_ecu, -1): return False, "Replay detected"
        if not hmac.compare_digest(frame.auth_tag, self.tag(frame)): return False, "Integrity failure"
        last_counters[frame.source_ecu] = frame.sequence_counter
        return True, "Authenticated"

