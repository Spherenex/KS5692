"""Synchronous OCPP 2.0.1 subset transported over a real local WebSocket."""
import json
import threading
import uuid
from websockets.sync.client import connect
from models import now_iso


class OCPPClient:
    def __init__(self, uri="ws://127.0.0.1:9010", station_id="KS5692-CS-01"):
        self.uri, self.station_id = uri, station_id
        self.socket = None
        self.lock = threading.RLock()

    @property
    def connected(self):
        return self.socket is not None

    def connect(self):
        if not self.connected:
            self.socket = connect(f"{self.uri}/{self.station_id}", subprotocols=["ocpp2.0.1"], open_timeout=2)
        return True

    def disconnect(self):
        with self.lock:
            if self.socket:
                try:self.socket.close()
                finally:self.socket = None

    def message(self,kind,payload=None):
        message_id = uuid.uuid4().hex
        return {"messageTypeId": 2, "messageId": message_id, "action": kind,
                "stationId": self.station_id, "timestamp": now_iso(), "payload": payload or {},
                "wireFrame": [2, message_id, kind, payload or {}]}

    def call(self,kind,payload=None):
        with self.lock:
            msg = self.message(kind,payload)
            try:
                self.connect()
                self.socket.send(json.dumps(msg["wireFrame"],separators=(",", ":")))
                frame = json.loads(self.socket.recv(timeout=3))
                if frame[0] == 4:
                    raise RuntimeError(f"{frame[2]}: {frame[3]}")
                if frame[0] != 3 or frame[1] != msg["messageId"]:
                    raise RuntimeError("Mismatched OCPP response")
                return msg, frame[2]
            except Exception:
                self.disconnect()
                raise
