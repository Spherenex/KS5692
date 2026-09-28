import time, uuid

class ChargingStation:
    def __init__(self): self.reset()
    def reset(self):
        self.status="Available"; self.connector="Disconnected"; self.authorized=False; self.voltage=0.; self.current=0.; self.power_kw=0.; self.energy_kwh=0.; self.started=None; self.ended=None; self.transaction_id=None; self.initial_soc=None; self.final_soc=None
    def connect(self):
        if self.connector=="Disconnected":
            self.energy_kwh=0.; self.started=None; self.ended=None; self.transaction_id=None; self.initial_soc=None; self.final_soc=None
        self.connector="Connected"; self.status="Preparing"
    def disconnect(self):
        self.connector="Disconnected"; self.status="Available"; self.authorized=False; self.voltage=0.; self.current=0.; self.power_kw=0.
    def authorize(self):
        if self.connector=="Connected": self.authorized=True; self.status="Authorizing"; return True
        return False
    def start(self,initial_soc=None):
        if self.connector=="Connected" and self.authorized:
            self.status="Charging"; self.started=time.time(); self.ended=None; self.initial_soc=initial_soc; self.final_soc=None; self.transaction_id="TX-"+uuid.uuid4().hex[:8].upper(); return True
        return False
    def stop(self,final_soc=None):
        if self.status=="Charging": self.status="Completed"; self.ended=time.time(); self.final_soc=final_soc; self.current=0.; self.power_kw=0.; return True
        return False
    @property
    def duration_seconds(self):
        if not self.started:return 0.
        return max(0.,(self.ended or time.time())-self.started)
    def tick(self,dt=.75):
        if self.status=="Charging":
            self.voltage=402.; self.current=48.; self.power_kw=self.voltage*self.current/1000; self.energy_kwh+=self.power_kw*dt/3600
        elif self.connector=="Connected": self.voltage=390.; self.current=0.; self.power_kw=0.
