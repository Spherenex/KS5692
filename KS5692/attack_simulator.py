class AttackSimulator:
    @staticmethod
    def replay(frame): frame.sequence_counter=max(0,frame.sequence_counter-5); return frame
    @staticmethod
    def unauthorized(frame): frame.source_ecu="UNKNOWN_ECU"; return frame
    @staticmethod
    def modified(frame): frame.payload={**frame.payload,"tampered":True}; return frame

