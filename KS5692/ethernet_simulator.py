import random, time

class EthernetSimulator:
    def transmit(self,packet,state):
        capacity=state.capacity
        traffic=state.vehicle.get("adas",120)+18
        if state.mode=="Network Failure Mode": return False,0,traffic
        overload=max(0,traffic-capacity)/capacity
        drop=random.random() < overload*(packet.priority/4)
        if not drop: packet.receive_timestamp=time.time()+(.00015*packet.priority)+overload*.004
        return not drop,(packet.receive_timestamp-packet.created_timestamp)*1000 if not drop else 0,traffic

