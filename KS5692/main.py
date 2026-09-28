# python dashboard.py



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
from verilog_bridge import VerilogSimulationBridge

class SimulationEngine:
    def __init__(self,db=None,csms_port=9010,verilog=None):
        self.ecus=ECUSimulator(); self.can=CANXLSimulator(); self.security=SecurityManager(); self.gateway=Gateway(); self.tsn=TSNScheduler(); self.ethernet=EthernetSimulator()
        self.csms=CSMSServer(port=csms_port); self.ocpp=OCPPClient(self.csms.uri); self.db=db or Database()
        self.verilog=verilog or VerilogSimulationBridge(); self._backend_announced_run=None
    def ocpp_send(self,s,kind,payload=None):
        online=s.mode!="OCPP Connection Failure Mode"
        if online:
            try:
                if not self.csms.running and not self.csms.start(): raise ConnectionError("CSMS failed to start")
                msg,response=self.ocpp.call(kind,payload)
                entry={"time":now_iso(),"type":kind,"direction":"Station → CSMS","payload":msg,"response":response}
                s.ocpp_messages.appendleft(entry); s.modules["OCPP"]="ONLINE"; s.modules["CSMS"]="ONLINE"
                s.log("OCPP",f"{kind} CALL sent over WebSocket")
                s.log("CSMS",f"{kind} CALLRESULT: {response.get('status','Accepted')}")
            except Exception as exc:
                online=False
                msg=self.ocpp.message(kind,payload)
                entry={"time":now_iso(),"type":kind,"direction":"Station → CSMS","payload":msg,"response":{"status":"QUEUED","error":str(exc)}}
                s.unsent_ocpp.append(entry); s.modules["OCPP"]="OFFLINE"; s.modules["CSMS"]="OFFLINE"
                s.log("OCPP",f"{kind} queued after transport failure: {exc}")
        else:
            self.ocpp.disconnect()
            msg=self.ocpp.message(kind,payload)
            entry={"time":now_iso(),"type":kind,"direction":"Station → CSMS","payload":msg,"response":{"status":"QUEUED"}}
            s.unsent_ocpp.append(entry); s.modules["OCPP"]="OFFLINE"; s.modules["CSMS"]="OFFLINE"
            s.log("OCPP",f"{kind} queued offline")
        s.stats["ocpp"]+=1
        self.db.ocpp_message(s.run_id,entry)
        return entry
    def boot(self,s): self.ocpp_send(s,"BootNotification",{"reason":"PowerUp"})

    def sync_ocpp_queue(self,s):
        if s.mode=="OCPP Connection Failure Mode": return 0
        queued=list(s.unsent_ocpp); s.unsent_ocpp.clear(); sent=0
        for index,entry in enumerate(queued):
            result=self.ocpp_send(s,entry["type"],entry["payload"].get("payload",{}))
            if result["response"].get("status")=="QUEUED":
                s.unsent_ocpp.extend(queued[index+1:])
                break
            sent+=1
        if sent:s.log("OCPP",f"Synchronized {sent} queued message(s)")
        return sent

    def record_charging_session(self,s):
        if s.charger.transaction_id and s.charger.ended:
            self.db.charging_session(s.run_id,s.charger)

    def inject(self,s,kind):
        if not s.can_frames:return
        frame=copy.deepcopy(s.can_frames[0]); frame={"Replay":AttackSimulator.replay,"Unauthorized":AttackSimulator.unauthorized,"Modified":AttackSimulator.modified}[kind](frame)
        ok,reason=self.security.verify(frame,s.verified_counters); s.stats["attacks"]+=1
        if not ok:s.stats["blocked"]+=1;s.stats["rejected"]+=1
        event={"time":now_iso(),"type":kind,"detected":not ok,"blocked":not ok,"reason":reason}
        s.security_events.appendleft(event); self.db.security_event(s.run_id,event); s.log("ATTACK",f"{kind}: {reason}")
    def tick(self,s):
        if not s.running or s.paused:return
        now=time.time()
        if s.mode=="Network Failure Mode" and s.network_failure_started is None:
            s.network_failure_started=now; s.log("ETHERNET","Link failure started")
        elif s.mode!="Network Failure Mode" and s.network_failure_started is not None:
            s.last_recovery_ms=(now-s.network_failure_started)*1000; s.network_failure_started=None
            s.log("ETHERNET",f"Link recovered after {s.last_recovery_ms:.0f} ms")
        if s.mode!="OCPP Connection Failure Mode" and s.unsent_ocpp:self.sync_ocpp_queue(s)
        s.tick_count+=1; s.charger.tick(.75/s.speed_factor)
        rtl_tick=self.verilog.step(s)
        ecus=rtl_tick.ecus if rtl_tick else self.ecus.update(s)
        if self._backend_announced_run != s.run_id:
            self._backend_announced_run=s.run_id
            if rtl_tick:
                s.log("SYSTEM","Simulation backend: SystemVerilog RTL (Icarus Verilog)")
            else:
                s.log("SYSTEM",f"Simulation backend: Python compatibility; {self.verilog.last_error}")
        frames=self.can.generate(ecus,s.counters,self.security)
        delivered=0; latencies=[]; waits=[]; traffic=s.vehicle.get("adas",120)+18; converted=[]
        for frame in frames:
            s.can_frames.appendleft(frame); s.stats["can"]+=1; s.log("CAN-XL",f"{frame.source_ecu} {frame.message_id} → Gateway counter={frame.sequence_counter}")
            packet,reason,process=self.gateway.convert(frame,self.security,s.verified_counters)
            if not packet:s.stats["rejected"]+=1;s.log("SECURITY",f"{frame.message_id} rejected: {reason}");continue
            s.stats["converted"]+=1; converted.append(packet); s.log("GATEWAY",f"{frame.message_id} → Ethernet {packet.traffic_class}; AES-GCM protected")
        if rtl_tick:
            scheduled=[]
            for packet in sorted(converted,key=lambda item:item.priority):
                decision=rtl_tick.decisions[packet.source]
                packet.tsn_enqueue_timestamp=packet.created_timestamp
                packet.tsn_dequeue_timestamp=packet.created_timestamp+decision.wait_ms/1000
                packet.queue_wait_ms=decision.wait_ms
                packet.transmission_time_ms=max(0,decision.latency_ms-decision.wait_ms)
                scheduled.append((packet,decision.wait_ms))
        else:
            scheduled=self.tsn.schedule_batch(converted,s.capacity)
        for packet,wait in scheduled:
            waits.append(wait); s.log("TSN",f"{packet.packet_id} priority={packet.priority} wait={wait:.3f} ms")
            decrypted,security_reason=self.security.verify_ethernet(packet)
            if decrypted is None:
                s.stats["rejected"]+=1; s.log("SECURITY",f"{packet.packet_id} rejected: {security_reason}"); continue
            if rtl_tick:
                decision=rtl_tick.decisions[packet.source]
                ok,latency=decision.delivered,decision.latency_ms if decision.delivered else 0
                if ok: packet.receive_timestamp=packet.created_timestamp+latency/1000
            else:
                ok,latency,traffic=self.ethernet.transmit(packet,s)
            if ok:
                s.stats["delivered"]+=1;delivered+=1;latencies.append(latency);s.packets.appendleft(packet)
                s.log("ETHERNET",f"{packet.packet_id} delivered in {latency:.3f} ms; integrity verified")
            else:s.stats["dropped"]+=1;s.log("ETHERNET",f"{packet.packet_id} dropped")
        latency=sum(latencies)/len(latencies) if latencies else 0; jitter=abs(latency-s.last_latency);s.last_latency=latency;s.last_jitter=jitter;s.latency_warning=latency>1
        utilization=min(100,traffic/s.capacity*100)
        throughput=min(traffic,s.capacity)*delivered/max(1,len(converted))
        s.history.append({"time":time.strftime("%H:%M:%S"),**s.vehicle,"latency":latency,"jitter":jitter,"queue_wait":sum(waits)/len(waits) if waits else 0,
                          "throughput":throughput,"packet_loss":100*s.stats["dropped"]/max(1,s.stats["converted"]),"utilization":utilization})
        s.log("SYSTEM",f"Tick {s.tick_count}: {delivered}/{len(frames)} packets delivered")
        if s.mode=="Cyberattack Mode" and s.tick_count%5==0:self.inject(s,["Replay","Unauthorized","Modified"][(s.tick_count//5)%3])
        if s.charger.status=="Charging" and s.tick_count%3==0:self.ocpp_send(s,"MeterValues",{"evseId":1,"meterValue":[{"timestamp":now_iso(),"sampledValue":[{"measurand":"Energy.Active.Import.Register","value":s.charger.energy_kwh,"unitOfMeasure":{"unit":"kWh"}},{"measurand":"SoC","value":s.vehicle["soc"],"unitOfMeasure":{"unit":"Percent"}},{"measurand":"Power.Active.Import","value":s.charger.power_kw,"unitOfMeasure":{"unit":"kW"}}]}]})
        if s.tick_count%5==0:
            stamp=now_iso(); v=s.vehicle
            self.db.execute("INSERT INTO vehicle_metrics VALUES(?,?,?,?,?,?,?,?)",(s.run_id,stamp,v.get("speed",0),v.get("soc",0),v.get("voltage",0),v.get("current",0),v.get("rpm",0),v.get("motor_temp",0)))
            self.db.execute("INSERT INTO network_metrics VALUES(?,?,?,?,?,?,?)",(s.run_id,stamp,latency,jitter,throughput,100*s.stats["dropped"]/max(1,s.stats["converted"]),utilization))
