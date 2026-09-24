import time, uuid

class ChargingStation:
    def __init__(self): self.reset()
    def reset(self):
        self.status="Available"; self.connector="Disconnected"; self.authorized=False; self.voltage=0.; self.current=0.; self.power_kw=0.; self.energy_kwh=0.; self.started=None; self.transaction_id=None
    def connect(self): self.connector="Connected"; self.status="Preparing"
    def disconnect(self): self.reset()
    def authorize(self):
        if self.connector=="Connected": self.authorized=True; self.status="Authorizing"; return True
        return False
    def start(self):
        if self.connector=="Connected" and self.authorized:
            self.status="Charging"; self.started=time.time(); self.transaction_id="TX-"+uuid.uuid4().hex[:8].upper(); return True
        return False
    def stop(self):
        if self.status=="Charging": self.status="Completed"; return True
        return False
    def tick(self,dt=.75):
        if self.status=="Charging":
            self.voltage=402.; self.current=48.; self.power_kw=self.voltage*self.current/1000; self.energy_kwh+=self.power_kw*dt/3600
        elif self.connector=="Connected": self.voltage=390.; self.current=0.; self.power_kw=0.

