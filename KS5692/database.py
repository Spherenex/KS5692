import json, sqlite3
from datetime import datetime
from config import DB_PATH

SCHEMA="""
CREATE TABLE IF NOT EXISTS simulation_runs(run_id TEXT PRIMARY KEY,start_time TEXT,end_time TEXT,mode TEXT,capacity INTEGER);
CREATE TABLE IF NOT EXISTS vehicle_metrics(run_id TEXT,timestamp TEXT,speed REAL,soc REAL,voltage REAL,current REAL,rpm REAL,motor_temperature REAL);
CREATE TABLE IF NOT EXISTS network_metrics(run_id TEXT,timestamp TEXT,latency REAL,jitter REAL,throughput REAL,packet_loss REAL,utilization REAL);
CREATE TABLE IF NOT EXISTS security_events(run_id TEXT,timestamp TEXT,attack_type TEXT,detected INTEGER,blocked INTEGER);
CREATE TABLE IF NOT EXISTS charging_sessions(run_id TEXT,transaction_id TEXT,start_time TEXT,end_time TEXT,initial_soc REAL,final_soc REAL,energy REAL,duration REAL);
CREATE TABLE IF NOT EXISTS ocpp_messages(run_id TEXT,timestamp TEXT,message_type TEXT,direction TEXT,payload TEXT,response TEXT);
"""
class Database:
    def __init__(self,path=DB_PATH):
        self.path=path
        with sqlite3.connect(self.path,timeout=3) as c:c.executescript(SCHEMA)
    def execute(self,sql,args=()):
        with sqlite3.connect(self.path,timeout=3) as c:c.execute(sql,args)

    def security_event(self,run_id,event):
        self.execute("INSERT INTO security_events VALUES(?,?,?,?,?)",
                     (run_id,event["time"],event["type"],int(event["detected"]),int(event["blocked"])))

    def ocpp_message(self,run_id,entry):
        self.execute("INSERT INTO ocpp_messages VALUES(?,?,?,?,?,?)",
                     (run_id,entry["time"],entry["type"],entry["direction"],
                      json.dumps(entry["payload"]),json.dumps(entry["response"])))

    def charging_session(self,run_id,charger):
        self.execute("INSERT INTO charging_sessions VALUES(?,?,?,?,?,?,?,?)",
                     (run_id,charger.transaction_id,
                      datetime.fromtimestamp(charger.started).isoformat() if charger.started else None,
                      datetime.fromtimestamp(charger.ended).isoformat() if charger.ended else None,
                      charger.initial_soc,charger.final_soc,charger.energy_kwh,charger.duration_seconds))
