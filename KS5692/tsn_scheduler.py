import time

class TSNScheduler:
    windows={1:(0,1,"Safety"),2:(1,3,"Control"),3:(3,6,"ADAS"),4:(6,10,"Normal")}
    def __init__(self):
        self.next_available = 0.0

    def active(self):
        ms=(time.time()*1000)%10
        for p,(a,b,n) in self.windows.items():
            if a<=ms<b:return p,n,ms
        return 4,"Normal",ms
    def _gate_start(self, ready, priority, transmission_ms):
        start_ms, end_ms, _ = self.windows[priority]
        candidate = ready * 1000
        cycle = candidate - (candidate % 10)
        position = candidate % 10
        if position < start_ms:
            candidate = cycle + start_ms
        elif position + transmission_ms > end_ms:
            candidate = cycle + 10 + start_ms
        return candidate / 1000

    def schedule(self,packet,capacity_mbps=1000):
        packet.tsn_enqueue_timestamp=time.time()
        transmission_ms = packet.size_bytes * 8 / max(1, capacity_mbps * 1_000_000) * 1000
        ready=max(packet.tsn_enqueue_timestamp,self.next_available)
        start=self._gate_start(ready,packet.priority,transmission_ms)
        packet.tsn_dequeue_timestamp=start
        packet.queue_wait_ms=max(0,(start-packet.tsn_enqueue_timestamp)*1000)
        packet.transmission_time_ms=transmission_ms
        self.next_available=start+transmission_ms/1000
        return packet,packet.queue_wait_ms

    def schedule_batch(self, packets, capacity_mbps=1000):
        # Critical traffic enters the gate first when several ECU messages
        # arrive during the same simulator tick.
        return [self.schedule(packet,capacity_mbps) for packet in sorted(packets,key=lambda p:p.priority)]
