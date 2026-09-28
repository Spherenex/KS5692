import time, uuid
from models import EthernetPacket

class Gateway:
    def convert(self, frame, security, last_counters):
        started=time.perf_counter(); valid,reason=security.verify(frame,last_counters)
        if not valid: return None,reason,(time.perf_counter()-started)*1000
        packet=EthernetPacket(str(uuid.uuid4())[:8],frame.source_ecu,"BACKBONE",frame.message_id,
            {1:"Critical",2:"Control",3:"High Bandwidth",4:"Normal"}[frame.priority],frame.priority,frame.payload,
            time.time(),time.time(),frame.frame_size,"AUTHENTICATED")
        security.protect_ethernet(packet)
        return packet,"Converted and encrypted",(time.perf_counter()-started)*1000
