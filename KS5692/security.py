import base64, hashlib, hmac, json, os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from config import ECU_IDS

class SecurityManager:
    def __init__(self, key=b"ks5692-educational-key"):
        self.key = key
        self.ethernet_key = hashlib.sha256(key + b"-macsec").digest()
        self.aesgcm = AESGCM(self.ethernet_key)

    def tag(self, frame):
        raw = f"{frame.message_id}|{frame.source_ecu}|{frame.sequence_counter}|{json.dumps(frame.payload, sort_keys=True)}".encode()
        return hmac.new(self.key, raw, hashlib.sha256).hexdigest()[:20]

    def sign(self, frame):
        frame.auth_tag = self.tag(frame); frame.authentication_status = "AUTHENTICATED"; return frame

    def verify(self, frame, last_counters):
        if frame.source_ecu not in {"BMS", "MCU", "VCU", "ADAS", "CCU"}: return False, "Unauthorized source"
        if ECU_IDS.get(frame.source_ecu) != frame.message_id: return False, "CAN ID/source mismatch"
        if frame.sequence_counter <= last_counters.get(frame.source_ecu, -1): return False, "Replay detected"
        if not hmac.compare_digest(frame.auth_tag, self.tag(frame)): return False, "Integrity failure"
        last_counters[frame.source_ecu] = frame.sequence_counter
        return True, "Authenticated"

    def protect_ethernet(self, packet):
        """Represent MACsec principles with authenticated AES-GCM encryption."""
        nonce = os.urandom(12)
        aad = f"{packet.packet_id}|{packet.source}|{packet.destination}|{packet.priority}".encode()
        plaintext = json.dumps(packet.payload, sort_keys=True, separators=(",", ":")).encode()
        encrypted = self.aesgcm.encrypt(nonce, plaintext, aad)
        packet.macsec_nonce = base64.b64encode(nonce).decode()
        packet.macsec_ciphertext = base64.b64encode(encrypted[:-16]).decode()
        packet.macsec_tag = base64.b64encode(encrypted[-16:]).decode()
        packet.security_status = "AUTHENTICATED + ENCRYPTED"
        return packet

    def verify_ethernet(self, packet):
        try:
            nonce = base64.b64decode(packet.macsec_nonce)
            encrypted = base64.b64decode(packet.macsec_ciphertext) + base64.b64decode(packet.macsec_tag)
            aad = f"{packet.packet_id}|{packet.source}|{packet.destination}|{packet.priority}".encode()
            plaintext = self.aesgcm.decrypt(nonce, encrypted, aad)
            return json.loads(plaintext), "MACsec integrity verified"
        except Exception:
            return None, "Ethernet integrity failure"
