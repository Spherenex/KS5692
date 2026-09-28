"""Small local OCPP 2.0.1 WebSocket CSMS used by the simulation."""
import json
import threading
from datetime import datetime, timezone
from websockets.sync.server import serve


class CSMSServer:
    def __init__(self, host="127.0.0.1", port=9010):
        self.host, self.port = host, port
        self.uri = f"ws://{host}:{port}"
        self._server = None
        self._thread = None
        self._ready = threading.Event()
        self.messages = []
        self.transactions = {}

    @property
    def running(self):
        return bool(self._server and self._thread and self._thread.is_alive())

    def start(self):
        if self.running:
            return True
        self._ready.clear()

        def run():
            try:
                with serve(self._connection, self.host, self.port, subprotocols=["ocpp2.0.1"]) as server:
                    self._server = server
                    self._ready.set()
                    server.serve_forever()
            finally:
                self._server = None
                self._ready.set()

        self._thread = threading.Thread(target=run, daemon=True, name="ks5692-csms")
        self._thread.start()
        self._ready.wait(2)
        return self.running

    def stop(self):
        if self._server:
            self._server.shutdown()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=2)

    def _connection(self, websocket):
        for raw in websocket:
            frame = None
            try:
                frame = json.loads(raw)
                response = self.handle_frame(frame)
            except Exception as exc:
                request_id = frame[1] if isinstance(frame, list) and len(frame) > 1 else "unknown"
                response = [4, request_id, "FormationViolation", str(exc), {}]
            websocket.send(json.dumps(response, separators=(",", ":")))

    def handle_frame(self, frame):
        if not isinstance(frame, list) or len(frame) != 4 or frame[0] != 2:
            raise ValueError("Expected OCPP CALL [2, messageId, action, payload]")
        _, message_id, action, payload = frame
        if not isinstance(payload, dict):
            raise ValueError("OCPP payload must be an object")
        response = self.handle({"messageType": action, "payload": payload})
        self.messages.append({"id": message_id, "action": action, "payload": payload, "response": response})
        return [3, message_id, response]

    def handle(self, message):
        action, payload = message["messageType"], message.get("payload", {})
        now = datetime.now(timezone.utc).isoformat()
        if action == "BootNotification":
            return {"currentTime": now, "interval": 30, "status": "Accepted"}
        if action == "Authorize":
            token = payload.get("idToken", {})
            token_value = token.get("idToken", "") if isinstance(token, dict) else str(token)
            status = "Accepted" if token_value.startswith("DEMO-") else "Invalid"
            return {"idTokenInfo": {"status": status}, "status": status}
        if action == "TransactionEvent":
            tx = payload.get("transactionInfo", {})
            transaction_id = tx.get("transactionId") or payload.get("transactionId")
            event_type = payload.get("eventType", "Updated")
            if transaction_id:
                self.transactions[transaction_id] = event_type
            return {"status": "Accepted", "transactionId": transaction_id}
        if action in {"MeterValues", "StatusNotification"}:
            return {"status": "Accepted"}
        return {"status": "NotSupported"}
