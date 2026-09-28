import copy, time, uuid
from collections import deque
from config import MAX_HISTORY, MAX_LOGS, MODULES
from charging_station import ChargingStation

class SimulationState:
    def __init__(self): self.reset()
    def reset(self):
        self.running=False; self.paused=False; self.mode="Normal Mode"; self.speed_factor=1.; self.capacity=1000
        self.run_id="RUN-"+uuid.uuid4().hex[:8].upper(); self.started=None; self.tick_count=0
        self.modules={m:"OFFLINE" for m in MODULES}; self.vehicle={"speed":0.,"soc":78.,"drive_mode":"Drive"}
        self.history=deque(maxlen=MAX_HISTORY); self.can_frames=deque(maxlen=100); self.packets=deque(maxlen=100)
        self.logs=deque(maxlen=MAX_LOGS); self.security_events=deque(maxlen=100); self.ocpp_messages=deque(maxlen=100)
        self.counters={}; self.verified_counters={}; self.stats={"can":0,"converted":0,"rejected":0,"delivered":0,"dropped":0,"attacks":0,"blocked":0,"ocpp":0}
        self.charger=ChargingStation(); self.unsent_ocpp=[]; self.last_latency=0.
        self.last_jitter=0.; self.network_failure_started=None; self.last_recovery_ms=0.; self.latency_warning=False
    def start(self):
        self.running=True; self.paused=False; self.started=time.time(); self.modules={m:"ONLINE" for m in MODULES}; self.modules["EV Charger"]="AVAILABLE"
    def stop(self): self.running=False; self.paused=False; self.modules={m:"OFFLINE" for m in MODULES}
    def log(self,cat,msg): self.logs.appendleft({"time":time.strftime("%H:%M:%S"),"category":cat,"message":msg})
