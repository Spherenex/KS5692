import random, time

class EthernetSimulator:
    def transmit(self,packet,state):
        capacity=state.capacity
        traffic=state.vehicle.get("adas",120)+18
        if state.mode=="Network Failure Mode": return False,0,traffic
        overload=max(0,traffic-capacity)/max(traffic,1)
        drop=random.random() < min(.98,overload*(.35+.15*packet.priority))
        congestion_ms=overload*(.45+.35*packet.priority)
        propagation_ms=.08+.025*packet.priority
        if not drop:
            packet.receive_timestamp=max(time.time(),packet.tsn_dequeue_timestamp)+(packet.transmission_time_ms+congestion_ms+propagation_ms)/1000
        return not drop,(packet.receive_timestamp-packet.created_timestamp)*1000 if not drop else 0,traffic
