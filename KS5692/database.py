import json, sqlite3
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
    def __init__(self):
        with sqlite3.connect(DB_PATH,timeout=3) as c:c.executescript(SCHEMA)
    def execute(self,sql,args=()):
        with sqlite3.connect(DB_PATH,timeout=3) as c:c.execute(sql,args)

