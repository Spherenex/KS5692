import time
from models import CANFrame, now_iso
from config import ECU_IDS

class CANXLSimulator:
    def generate(self, ecus, counters, security):
        frames=[]
        for ecu in ecus:
            src=ecu.ecu_name; counters[src]=counters.get(src,0)+1
            priority={"VCU":1,"BMS":2,"MCU":2,"ADAS":3,"CCU":2}[src]
            frame=CANFrame(ECU_IDS[src],src,"GATEWAY",priority,now_iso(),ecu.parameters,counters[src],frame_size=min(2048,32+len(str(ecu.parameters))))
            frames.append(security.sign(frame))
        return frames

