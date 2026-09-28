class AttackSimulator:
    @staticmethod
    def replay(frame): frame.sequence_counter=max(0,frame.sequence_counter-5); return frame
    @staticmethod
    def unauthorized(frame): frame.source_ecu="UNKNOWN_ECU"; return frame
    @staticmethod
    def modified(frame):
        # Use a fresh counter so verification reaches the integrity check; the
        # stale authentication tag then proves the payload was modified.
        frame.sequence_counter += 1
        frame.payload={**frame.payload,"tampered":True}
        return frame
