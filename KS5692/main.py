import copy, json, time
from ecu_simulator import ECUSimulator
from canxl_simulator import CANXLSimulator
from security import SecurityManager
from gateway import Gateway
from tsn_scheduler import TSNScheduler
from ethernet_simulator import EthernetSimulator
from ocpp_client import OCPPClient
from csms_server import CSMSServer
from attack_simulator import AttackSimulator
from models import now_iso
from database import Database

class SimulationEngine:
    def __init__(self):
        self.ecus=ECUSimulator(); self.can=CANXLSimulator(); self.security=SecurityManager(); self.gateway=Gateway(); self.tsn=TSNScheduler(); self.ethernet=EthernetSimulator(); self.ocpp=OCPPClient(); self.csms=CSMSServer(); self.db=Database()
    def ocpp_send(self,s,kind,payload=None):
        msg=self.ocpp.message(kind,payload); online=s.mode!="OCPP Connection Failure Mode"
        entry={"time":now_iso(),"type":kind,"direction":"Station → CSMS","payload":msg,"response":self.csms.handle(msg) if online else {"status":"QUEUED"}}
        (s.ocpp_messages if online else s.unsent_ocpp).appendleft(entry) if online else s.unsent_ocpp.append(entry)
        s.stats["ocpp"]+=1; s.log("OCPP",f"{kind} {'accepted' if online else 'queued offline'}")
    def boot(self,s): self.ocpp_send(s,"BootNotification",{"reason":"PowerUp"})
    def inject(self,s,kind):
        if not s.can_frames:return
        frame=copy.deepcopy(s.can_frames[0]); frame={"Replay":AttackSimulator.replay,"Unauthorized":AttackSimulator.unauthorized,"Modified":AttackSimulator.modified}[kind](frame)
        ok,reason=self.security.verify(frame,s.verified_counters); s.stats["attacks"]+=1
        if not ok:s.stats["blocked"]+=1;s.stats["rejected"]+=1
        s.security_events.appendleft({"time":now_iso(),"type":kind,"detected":not ok,"blocked":not ok,"reason":reason}); s.log("ATTACK",f"{kind}: {reason}")
    def tick(self,s):
        if not s.running or s.paused:return
        s.tick_count+=1; s.charger.tick(.75/s.speed_factor); ecus=self.ecus.update(s)
        frames=self.can.generate(ecus,s.counters,self.security)
        delivered=0; latencies=[]; traffic=s.vehicle.get("adas",120)+18
        for frame in frames:
            s.can_frames.appendleft(frame); s.stats["can"]+=1
            packet,reason,process=self.gateway.convert(frame,self.security,s.verified_counters)
            if not packet:s.stats["rejected"]+=1;continue
            s.stats["converted"]+=1; packet,wait=self.tsn.schedule(packet); ok,latency,traffic=self.ethernet.transmit(packet,s)
            if ok:s.stats["delivered"]+=1;delivered+=1;latencies.append(latency);s.packets.appendleft(packet)
            else:s.stats["dropped"]+=1
        latency=sum(latencies)/len(latencies) if latencies else 0; jitter=abs(latency-s.last_latency);s.last_latency=latency
        utilization=min(100,traffic/s.capacity*100); throughput=min(traffic,s.capacity)
        s.history.append({"time":time.strftime("%H:%M:%S"),**s.vehicle,"latency":latency,"jitter":jitter,"throughput":throughput,"packet_loss":100*s.stats["dropped"]/max(1,s.stats["converted"]),"utilization":utilization})
        s.log("SYSTEM",f"Tick {s.tick_count}: {delivered}/{len(frames)} packets delivered")
        if s.mode=="Cyberattack Mode" and s.tick_count%5==0:self.inject(s,["Replay","Unauthorized","Modified"][(s.tick_count//5)%3])
        if s.charger.status=="Charging" and s.tick_count%3==0:self.ocpp_send(s,"MeterValues",{"SOC":s.vehicle["soc"],"Voltage":s.charger.voltage,"Current":s.charger.current,"Power":s.charger.power_kw,"Energy":s.charger.energy_kwh})
        if s.tick_count%5==0:
            stamp=now_iso(); v=s.vehicle
            self.db.execute("INSERT INTO vehicle_metrics VALUES(?,?,?,?,?,?,?,?)",(s.run_id,stamp,v.get("speed",0),v.get("soc",0),v.get("voltage",0),v.get("current",0),v.get("rpm",0),v.get("motor_temp",0)))
            self.db.execute("INSERT INTO network_metrics VALUES(?,?,?,?,?,?,?)",(s.run_id,stamp,latency,jitter,throughput,100*s.stats["dropped"]/max(1,s.stats["converted"]),utilization))
