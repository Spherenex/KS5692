"""Dash/Plotly dashboard for the KS5692 automotive network simulation."""
import json, threading, time
from functools import lru_cache
from urllib.parse import quote
import pandas as pd
import plotly.express as px
from dash import Dash, Input, Output, ctx, dcc, html, dash_table
from main import SimulationEngine
from metrics import summarize
from state_manager import SimulationState

sim, engine, lock = SimulationState(), SimulationEngine(), threading.RLock()

def worker():
    while True:
        with lock:
            if sim.running and not sim.paused:
                try: engine.tick(sim)
                except Exception as exc: sim.log("SYSTEM", f"Isolated simulator error: {exc}")
        time.sleep(max(.1, .75/sim.speed_factor))
threading.Thread(target=worker, daemon=True, name="ks5692-engine").start()

# update_title=None removes Dash's "Updating..." tab flicker on every interval tick.
app=Dash(__name__,title="Secure Automotive Ethernet & OCPP Simulation",suppress_callback_exceptions=True,update_title=None)
server=app.server
BUILD_ID = str(time.time_ns())

@server.get("/_ks5692-version")
def dashboard_version():
    return {"build": BUILD_ID}

# Dash callback definitions can change during development. Prevent an already
# open browser tab from reusing an old layout/dependency map after a restart.
@server.after_request
def disable_dashboard_caching(response):
    if response.content_type and ("text/html" in response.content_type or "application/json" in response.content_type):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

PAGES=["Overview","Live Vehicle","CAN XL","Gateway","Ethernet","TSN","Performance","Security","EV Charging","OCPP & CSMS","Logs","Comparison","Reports"]
MODES=["Normal Mode","High Traffic Mode","Cyberattack Mode","Network Failure Mode","OCPP Connection Failure Mode"]
VEHICLE_NODES=[("Vehicle ECUs","ECU"),("CAN XL","XL"),("Security","SEC"),("Gateway","GW"),("TSN","QBV"),("Automotive Ethernet","ETH")]
CLOUD_NODES=[("EV Charger","EVSE"),("OCPP","OCPP"),("CSMS","CLOUD")]
NODES=VEHICLE_NODES+CLOUD_NODES
RINGS=[("g-speed","km/h","primary"),("g-soc","state of charge","success"),("g-rpm","motor rpm","violet")]
METERS=[("m-btemp","Battery temperature","success"),("m-mtemp","Motor temperature","warning"),
        ("m-adas","ADAS bandwidth","violet"),("m-torque","Torque demand","primary")]
CAN_COLUMNS=["Time","CAN ID","Source","Destination","Priority","Data","Counter","Authentication"]
GW_COLUMNS=["Packet","Source","CAN ID","Class","Priority","Security"]

# ---------------------------------------------------------------- primitives
def ratio(value,low,high): return max(0.,min(100.,(value-low)/(high-low)*100 if high>low else 0.))
def data_uri(mime,text): return f"data:{mime};charset=utf-8,"+quote(text)
def motion(): return "running" if sim.running and not sim.paused else "paused" if sim.running else "idle"

def kpi(label,value,tone="cyan"): return html.Div([html.Small(label),html.Strong(str(value),className=tone)],className="kpi")
def kpi_grid(items=(),cid=None):
 grid=html.Div([kpi(*i) for i in items],className="kpi-grid")
 if cid: grid.id=cid
 return grid
def head(eyebrow,title,lede=None):
 parts=[html.Span(eyebrow,className="eyebrow"),html.H2(title)]+([html.P(lede,className="lede")] if lede else [])
 return html.Div(parts,className="page-head")

def dots(count,step): return [html.I(style={"animationDelay":f"{-i*step:.2f}s"}) for i in range(count)]
def link(): return html.Div(dots(3,.8),className="link")
def node(index,name,tag,state,cls):
 return html.Div([html.Span(tag,className="node-tag"),html.B(name),html.Span(state,id=f"nodestat-{index}",className="node-state")],
                 id=f"node-{index}",className=cls)
def rail(pairs,offset,st):
 cells=[]
 for i,(name,tag) in enumerate(pairs):
  cells.append(node(offset+i,name,tag,st["states"][offset+i],st["classes"][offset+i]))
  if i<len(pairs)-1: cells.append(link())
 return html.Div(cells,className="rail")
def topology(st):
 return html.Div([
  html.Div([html.Span("In-vehicle domain",className="rail-label"),rail(VEHICLE_NODES,0,st)],className="rail-block"),
  html.Div([html.Div(dots(3,.7),className="vlink"),html.Span("Backbone handoff",className="bridge-label")],className="bridge"),
  html.Div([html.Span("Charging & cloud domain",className="rail-label"),rail(CLOUD_NODES,len(VEHICLE_NODES),st)],className="rail-block"),
 ],id="topo",className=st["topo"])

def ring(rid,label,tone,pct,value):
 return html.Div([html.Div(id=rid,className=f"ring-arc t-{tone}",style={"--p":f"{pct:.1f}"}),
                  html.Div([html.Strong(value,id=f"{rid}-v"),html.Small(label)],className="ring-core")],className="ring")
def meter(mid,label,tone,pct,value):
 return html.Div([html.Div([html.Small(label),html.B(value,id=f"{mid}-v")],className="meter-head"),
                  html.Div(html.I(id=mid,style={"--w":f"{pct:.1f}%"}),className=f"meter-track t-{tone}")],className="meter")
def lane(tag,chips,duration="22s"):
 items=[html.Span(text,className=f"chip {tone}") for text,tone in chips]
 return html.Div([html.Span(tag,className="lane-tag"),
                  html.Div(html.Div(items+items,className="stream-lane",style={"animationDuration":duration}),className="stream")],
                 className="lane")

def table(tid,columns,rows=()):
 return dash_table.DataTable(id=tid,data=list(rows),columns=[{"name":c,"id":c} for c in columns],page_size=12,style_as_list_view=True,
  style_table={"overflowX":"auto"},
  style_cell={"backgroundColor":"transparent","color":"#dce7f8","border":"none","borderBottom":"1px solid rgba(122,152,204,.13)",
              "fontFamily":"var(--mono)","fontSize":"12px","textAlign":"left","padding":"11px 14px","maxWidth":"360px",
              "overflow":"hidden","textOverflow":"ellipsis"},
  style_header={"backgroundColor":"rgba(122,152,220,.08)","color":"#94a8c6","fontWeight":"700","fontSize":"10px",
                "letterSpacing":"1.1px","textTransform":"uppercase","border":"none","borderBottom":"1px solid rgba(122,152,204,.24)"},
  style_data_conditional=[{"if":{"row_index":"odd"},"backgroundColor":"rgba(255,255,255,.015)"}])

def empty_figure(title):
 return {"data":[],"layout":{"template":"plotly_dark","height":380,"autosize":True,
  "paper_bgcolor":"rgba(0,0,0,0)","plot_bgcolor":"rgba(0,0,0,0)","font":{"color":"#a9b7cc"},
  "margin":{"l":35,"r":15,"t":52,"b":32},"uirevision":"stable","title":{"text":title,"x":.04},
  "annotations":[{"text":"Loading live data...","xref":"paper","yref":"paper","x":.5,"y":.5,
                  "showarrow":False,"font":{"color":"#718098","size":13}}],
  "xaxis":{"visible":False},"yaxis":{"visible":False}}}

def graph(gid,cols,title):
 # Native figure dictionaries are inexpensive, so provide the real current
 # figure immediately. The interval callback then keeps the same graph live.
 return dcc.Graph(id=gid,figure=line(cols,title),config={"displayModeBar":False,"responsive":True,"displaylogo":False},
                  responsive=True,className="chart")

# ------------------------------------------------------------------- layout
app.layout=html.Div([
 dcc.Interval(id="clock",interval=1000),
 dcc.Store(id="sink-controls"),dcc.Store(id="sink-attacks"),dcc.Store(id="sink-charge"),dcc.Store(id="sink-sync"),
 dcc.Store(id="sink-logs"),
 html.Div([html.Span(className="glow a"),html.Span(className="glow b")],className="backdrop"),
 html.Aside([
  html.Div([html.Div("KS",className="logo"),html.Div([html.B("KS5692"),html.Small("NETWORK LAB")])],className="brand"),
  html.Label("Simulation mode"),dcc.Dropdown(MODES,"Normal Mode",id="mode",clearable=False,className="dark-dropdown"),
  html.Label("Ethernet capacity"),
  dcc.Dropdown([{"label":"100 Mbps","value":100},{"label":"1 Gbps","value":1000}],1000,id="capacity",clearable=False,className="dark-dropdown"),
  html.Label("Simulation speed"),
  dcc.Dropdown([{"label":f"{x:g}×","value":x} for x in [.5,1,2,5]],1,id="speed",clearable=False,className="dark-dropdown"),
  # Initial disabled states match a fresh, stopped engine; the clock corrects
  # them within a tick for a browser that connects to an already-running run.
  html.Div([html.Button("START",id="start",className="go"),html.Button("PAUSE",id="pause",disabled=True),
            html.Button("RESUME",id="resume",disabled=True),html.Button("STOP",id="stop",disabled=True),
            html.Button("RESET",id="reset",className="danger")],className="controls"),
  html.Hr(),
  dcc.RadioItems(PAGES,"Overview",id="page",className="nav",labelClassName="nav-item"),
  html.P("Educational software simulation; not physical or certification-level protocol validation.",className="disclaimer"),
 ],className="sidebar"),
 html.Main([
  html.Header([
   html.Div([html.H1("Secure Automotive Ethernet & OCPP Simulation"),
             html.P("CAN XL • Automotive Ethernet • TSN • Security • EV Charging • OCPP 2.0.1")]),
   html.Div([html.Div([html.Span(className="dot"),html.Span("OFFLINE",id="status-text")],id="status",className="status offline"),
             html.Div([html.Small("Run"),html.B("—",id="meta-run")],className="meta"),
             html.Div([html.Small("Ticks"),html.B("0",id="meta-tick")],className="meta")],className="header-side"),
  ]),
  html.Div(id="content"),
 ],className="main"),
],className="shell")

# ---------------------------------------------------------------- page state
# Each page has one state function feeding both the initial render and the
# clock callback, so a freshly opened page shows real values immediately
# instead of placeholders that pop in on the next tick.
def ov_state():
 states=[sim.modules.get(name,"OFFLINE") for name,_ in NODES]
 frame=sim.can_frames[0] if sim.can_frames else None
 return {"states":states,"classes":["node active" if s!="OFFLINE" else "node" for s in states],"topo":f"topo {motion()}",
         "current":(f"{frame.source_ecu} · {frame.message_id} · Priority {frame.priority} · "
                    f"{frame.authentication_status} · {sim.last_latency:.3f} ms") if frame else "Waiting for simulation data",
         "cards":[("Frames signed",f'{sim.stats["can"]:,}',"cyan"),("Converted",f'{sim.stats["converted"]:,}',"green"),
                  ("Delivered",f'{sim.stats["delivered"]:,}',"green"),("Rejected",f'{sim.stats["rejected"]:,}',"red"),
                  ("Dropped",f'{sim.stats["dropped"]:,}',"amber"),("Latency",f"{sim.last_latency:.3f} ms","violet")]}

def veh_state():
 v=dict(sim.vehicle)
 speed,soc,rpm=v.get("speed",0),v.get("soc",0),v.get("rpm",0)
 btemp,mtemp=v.get("battery_temp",0),v.get("motor_temp",0)
 adas,torque=v.get("adas",0),v.get("torque",0)
 return {"rings":[(ratio(speed,0,160),f"{speed:.0f}"),(ratio(soc,0,100),f"{soc:.1f}%"),(ratio(rpm,0,8000),f"{rpm:.0f}")],
         "meters":[(ratio(btemp,15,55),f"{btemp:.1f} °C"),(ratio(mtemp,25,95),f"{mtemp:.1f} °C"),
                   (ratio(adas,0,800),f"{adas:.1f} Mbps"),(ratio(torque,0,250),f"{torque:.1f} Nm")],
         "cards":[("Speed",f"{speed:.1f} km/h","cyan"),("Battery SOC",f"{soc:.2f}%","green"),
                  ("Voltage",f'{v.get("voltage",0):.1f} V',"cyan"),("Current",f'{v.get("current",0):.1f} A',"amber"),
                  ("Motor RPM",f"{rpm:.0f}","cyan"),("ADAS",f"{adas:.1f} Mbps","violet"),
                  ("State of health",f'{v.get("soh",0):.0f}%',"green"),("Obstacle",f'{v.get("obstacle",0):.1f} m',"amber")]}

def can_state():
 status=sim.modules["CAN XL"]
 return {"rows":[{"Time":f.timestamp[11:23],"CAN ID":f.message_id,"Source":f.source_ecu,"Destination":f.destination,
                  "Priority":f.priority,"Data":json.dumps(f.payload),"Counter":f.sequence_counter,
                  "Authentication":f.authentication_status} for f in sim.can_frames],
         "pipe":f"pipe {motion()}",
         "cards":[("Status",status,"green" if status!="OFFLINE" else "muted"),("Frames",f'{sim.stats["can"]:,}',"cyan"),
                  ("Queue",len(sim.can_frames),"amber"),("Authenticated",f'{sim.stats["converted"]:,}',"green"),
                  ("Rejected",f'{sim.stats["rejected"]:,}',"red")]}

def gw_state():
 return {"rows":[{"Packet":p.packet_id,"Source":p.source,"CAN ID":p.original_can_id,"Class":p.traffic_class,
                  "Priority":p.priority,"Security":p.security_status} for p in sim.packets],
         "pipe":f"pipe {motion()}",
         "cards":[("Received",f'{sim.stats["can"]:,}',"cyan"),("Converted",f'{sim.stats["converted"]:,}',"green"),
                  ("Rejected",f'{sim.stats["rejected"]:,}',"red"),("Latency",f"{sim.last_latency:.3f} ms","amber")]}

def eth_state():
 failed=sim.mode=="Network Failure Mode"
 traffic=sim.vehicle.get("adas",0)+18; util=min(100.,traffic/sim.capacity*100)
 state="FAILURE" if failed else sim.modules["Automotive Ethernet"]
 return {"util":util,"label":f"{util:.1f}%","state":state,"panel":f"eth {'down' if failed else motion()}",
         "cards":[("Link",state,"red" if failed else "green" if state!="OFFLINE" else "muted"),
                  ("Capacity",f"{sim.capacity} Mbps","cyan"),("Traffic",f"{traffic:.1f} Mbps","amber"),
                  ("Available",f"{max(0,sim.capacity-traffic):.1f} Mbps","green"),
                  ("Utilisation",f"{util:.1f}%","violet"),("Dropped",f'{sim.stats["dropped"]:,}',"red")]}

def tsn_state():
 priority,name,ms=engine.tsn.active()
 return {"active":f"Active window: {name} · priority {priority} · {ms:.2f} ms into the 10 ms cycle",
         "cards":[(f"Priority {q} · {title}",sum(x.priority==q for x in sim.packets),"cyan" if q==priority else "muted")
                  for q,(_,_,title) in engine.tsn.windows.items()]}

def perf_state():
 m=summarize(list(sim.history)); loss=100*sim.stats["dropped"]/max(1,sim.stats["converted"])
 return {"cards":[("Latency",f"{sim.last_latency:.3f} ms","red" if sim.last_latency>1 else "green"),
                  ("Average latency",f'{m["avg_latency"]:.3f} ms',"cyan"),("Jitter",f'{m["avg_jitter"]:.3f} ms',"amber"),
                  ("Throughput",f'{m["avg_throughput"]:.1f} Mbps',"violet"),
                  ("Utilisation",f'{m["avg_utilization"]:.1f}%',"cyan"),("Loss",f"{loss:.2f}%","red")]}

def sec_state():
 breached=bool(sim.security_events)
 return {"radar":f"radar {'alert' if breached else motion()}","verdict":"BREACH" if breached else "SECURE",
         "log":"\n".join(f'[{e["time"][11:19]}] {e["type"]}: {e["reason"]}' for e in sim.security_events) or "No alerts",
         "cards":[("Status","ATTACK DETECTED" if breached else "SECURE","red" if breached else "green"),
                  ("Authenticated",f'{sim.stats["converted"]:,}',"green"),("Rejected",f'{sim.stats["rejected"]:,}',"red"),
                  ("Attacks",sim.stats["attacks"],"amber"),("Blocked",sim.stats["blocked"],"green")]}

def ev_state():
 c=sim.charger; soc=sim.vehicle.get("soc",78)
 return {"soc":ratio(soc,0,100),"label":f"{soc:.1f}%",
         "rig":f"rig {'charging' if c.status=='Charging' else 'linked' if c.connector=='Connected' else 'idle'}",
         "cards":[("Charger",c.status,"green" if c.status=="Charging" else "cyan"),("Connector",c.connector,"cyan"),
                  ("Authorization","ACCEPTED" if c.authorized else "REQUIRED","green" if c.authorized else "amber"),
                  ("SOC",f"{soc:.2f}%","green"),("Voltage",f"{c.voltage:.1f} V","cyan"),
                  ("Current",f"{c.current:.1f} A","amber"),("Power",f"{c.power_kw:.2f} kW","violet"),
                  ("Energy",f"{c.energy_kwh:.3f} kWh","green")]}

def ocpp_state():
 online=sim.mode!="OCPP Connection Failure Mode"
 return {"ws":f"ws {motion() if online else 'down'}","sync_disabled":(not online) or (not sim.unsent_ocpp),
         "log":"\n".join(f'[{x["time"][11:19]}] {x["direction"]} · {x["type"]} · {x["response"]["status"]}\n'
                         f'{json.dumps(x["payload"],indent=2)}' for x in list(sim.ocpp_messages)[:20]) or "Waiting for OCPP messages",
         "cards":[("WebSocket","CONNECTED" if online else "OFFLINE","green" if online else "red"),
                  ("Station","KS5692-CS-01","cyan"),("CSMS","ONLINE" if online else "OFFLINE","green" if online else "red"),
                  ("Transaction",sim.charger.transaction_id or "—","violet"),
                  ("Messages",f'{sim.stats["ocpp"]:,}',"cyan"),("Offline queue",len(sim.unsent_ocpp),"amber")]}

def logs_text(): return "\n".join(f'[{x["time"]}] [{x["category"]}] {x["message"]}' for x in sim.logs)

def snapshot():
 df=pd.DataFrame(list(sim.history))
 return {"simulation":{"run_id":sim.run_id,"mode":sim.mode,"capacity":sim.capacity,"ticks":sim.tick_count},
         "vehicle":{"soc":sim.vehicle.get("soc"),"speed":sim.vehicle.get("speed"),
                    "max_speed":float(df.speed.max()) if not df.empty else 0},
         "network":{**summarize(list(sim.history)),**sim.stats},
         "charging":{"transaction":sim.charger.transaction_id,"energy_kwh":sim.charger.energy_kwh},
         "ocpp":{"messages":sim.stats["ocpp"],"queued":len(sim.unsent_ocpp)}}

# -------------------------------------------------------------------- pages
def page_overview():
 st=ov_state()
 return html.Div([
  head("System","Integrated Communication Architecture",
       "Signed CAN XL frames pass the security gateway and TSN scheduler onto Automotive Ethernet, then out to the charging cloud."),
  topology(st),
  kpi_grid(st["cards"],cid="ov-kpis"),
  html.Div([html.Small("Current message on the bus"),html.Code(st["current"],id="ov-current")],className="strip"),
  html.Details([html.Summary("Demonstration sequence"),
                html.P("Start → ECUs → CAN XL → gateway/security → TSN/Ethernet → connect and authorize EV → "
                       "charging/OCPP → attacks → high traffic/failures → report.")],
               open=True,className="panel"),
 ],className="page")

def page_vehicle():
 st=veh_state()
 return html.Div([
  head("Telemetry","Live Vehicle","Five virtual ECUs publish signed telemetry on every simulation tick."),
  html.Div([
   html.Div([ring(rid,label,tone,pct,val) for (rid,label,tone),(pct,val) in zip(RINGS,st["rings"])],className="ring-row"),
   html.Div([meter(mid,label,tone,pct,val) for (mid,label,tone),(pct,val) in zip(METERS,st["meters"])],className="meter-stack"),
  ],className="cluster"),
  kpi_grid(st["cards"],cid="veh-kpis"),
  html.Div([graph("vehicle-a",["speed","rpm"],"Speed and RPM"),
            graph("vehicle-b",["soc","battery_temp","adas"],"SOC, Temperature, ADAS")],className="two"),
 ],className="page")

def page_can():
 st=can_state()
 chips=[("0x103 VCU","p1"),("0x101 BMS","p2"),("0x104 ADAS","p3"),("0x102 MCU","p2"),("0x105 CCU","p2"),
        ("0x103 VCU","p1"),("0x104 ADAS","p3"),("0x101 BMS","p2")]
 return html.Div([
  head("Bus","CAN XL Monitor","Software CAN XL simulation — not a physical CAN implementation."),
  html.Div([lane("CAN XL",chips,"24s")],id="can-bus",className=st["pipe"]),
  kpi_grid(st["cards"],cid="can-kpis"),
  table("can-table",CAN_COLUMNS,st["rows"]),
 ],className="page")

def page_gateway():
 st=gw_state()
 incoming=[("0x101 ok","ok"),("0x104 ok","ok"),("0x103 ok","ok"),("0x999 rejected","bad"),("0x102 ok","ok"),("0x105 ok","ok")]
 outgoing=[("Critical","p1"),("Control","p2"),("High Bandwidth","p3"),("Control","p2"),("Normal","p4"),("Critical","p1")]
 return html.Div([
  head("Conversion","Secure CAN XL / Ethernet Gateway",
       "Every frame is verified against its SecOC-style tag and counter before it becomes an Ethernet packet."),
  html.Div([lane("CAN XL in",incoming,"20s"),
            html.Div([html.Span("VERIFY"),html.Span("SIGN"),html.Span("CLASSIFY")],className="convert"),
            lane("Ethernet out",outgoing,"16s")],id="gw-pipe",className=st["pipe"]),
  kpi_grid(st["cards"],cid="gw-kpis"),
  table("gw-table",GW_COLUMNS,st["rows"]),
 ],className="page")

def page_ethernet():
 st=eth_state()
 return html.Div([
  head("Backbone","Automotive Ethernet","Bandwidth, utilisation and loss across the simulated switched backbone."),
  html.Div([
   html.Div([html.Span("Link",className="lane-tag"),html.Span(st["state"],id="eth-state",className="link-state")],className="eth-head"),
   html.Div(html.I(id="eth-fill",style={"--w":f'{st["util"]:.1f}%'}),className="band"),
   html.Div([html.Small("Utilisation"),html.B(st["label"],id="eth-util")],className="band-foot"),
  ],id="eth-panel",className=st["panel"]),
  kpi_grid(st["cards"],cid="eth-kpis"),
  graph("ethernet-graph",["throughput","utilization"],"Bandwidth and Utilisation"),
 ],className="page")

def page_tsn():
 st=tsn_state()
 slots=[("0 – 1 ms","SAFETY","safety"),("1 – 3 ms","CONTROL","control"),("3 – 6 ms","ADAS","adas"),("6 – 10 ms","NORMAL","normal")]
 return html.Div([
  head("Scheduling","TSN IEEE 802.1Qbv Simulation",
       "Gate windows repeat every 10 ms in the simulation; the animation below runs time-dilated so the cycle stays visible."),
  html.Div(st["active"],id="tsn-active",className="strip mono"),
  html.Div([html.Div([html.B(window),html.Span(name)],className=f"slot {cls}") for window,name,cls in slots]
           +[html.Div(html.I(),className="playhead")],className="timeline"),
  kpi_grid(st["cards"],cid="tsn-kpis"),
 ],className="page")

def page_performance():
 return html.Div([
  head("Quality","Network Performance","Latency, jitter, throughput and loss measured across the simulated path."),
  kpi_grid(perf_state()["cards"],cid="perf-kpis"),
  html.Div([graph("latency-graph",["latency","jitter"],"Latency and Jitter"),
            graph("throughput-graph",["throughput","packet_loss","utilization"],"Throughput, Loss, Utilisation")],className="two"),
 ],className="page")

def page_security():
 st=sec_state()
 return html.Div([
  head("Defence","Security Center","HMAC signing with replay protection. Injected attacks are local, simulated and safe."),
  html.Div([
   html.Div([html.Div(className="radar-sweep"),html.Div(className="radar-rings"),
             html.Div([html.Strong(st["verdict"],id="sec-verdict"),html.Small("gateway state")],className="radar-core")],
            id="sec-radar",className=st["radar"]),
   kpi_grid(st["cards"],cid="sec-kpis"),
  ],className="defence"),
  html.Div([html.Button("REPLAY ATTACK",id="replay"),html.Button("UNAUTHORIZED",id="unauthorized"),
            html.Button("MODIFIED PACKET",id="modified"),html.Button("CLEAR ALERTS",id="clear-alerts",className="ghost")],
           className="actions"),
  html.Pre(st["log"],id="sec-log",className="terminal"),
 ],className="page")

def page_charging():
 st=ev_state()
 return html.Div([
  head("Charging","EV Charging Station","A virtual DC charge point drives the CCU ECU and the OCPP transaction."),
  html.Div([html.Button("CONNECT EV",id="connect"),html.Button("AUTHORIZE",id="authorize"),
            html.Button("START CHARGING",id="charge"),html.Button("STOP CHARGING",id="stop-charge"),
            html.Button("DISCONNECT",id="disconnect",className="ghost")],className="actions"),
  html.Div([
   html.Div([html.Span("EVSE",className="rig-tag"),html.Div("⚡",className="rig-bolt"),html.Small("KS5692-CS-01")],className="evse"),
   html.Div(dots(4,.6),className="cable"),
   html.Div([html.Div(html.I(id="ev-fill",style={"--w":f'{st["soc"]:.1f}%'}),className="batt-shell"),
             html.B(st["label"],id="ev-soc-label")],className="batt"),
  ],id="ev-rig",className=st["rig"]),
  kpi_grid(st["cards"],cid="ev-kpis"),
  html.Div([graph("soc-graph",["soc"],"Battery state of charge"),
            graph("power-graph",["voltage","current"],"Voltage and Current")],className="two"),
 ],className="page")

def page_ocpp():
 st=ocpp_state()
 return html.Div([
  head("Cloud","OCPP 2.0.1 & CSMS","Structured station-to-CSMS messages, with local queueing while the link is down."),
  html.Div([
   html.Div([html.B("KS5692-CS-01"),html.Small("Charging station")],className="endpoint"),
   html.Div(dots(3,.75),className="link wide"),
   html.Div([html.B("CSMS"),html.Small("Central system")],className="endpoint"),
  ],id="ocpp-link",className=st["ws"]),
  kpi_grid(st["cards"],cid="ocpp-kpis"),
  html.Button("SYNCHRONIZE QUEUE",id="sync",disabled=st["sync_disabled"]),
  html.Pre(st["log"],id="ocpp-log",className="terminal tall"),
 ],className="page")

def page_logs():
 text=logs_text()
 return html.Div([
  head("Trace","Unified Communication Terminal","Every subsystem writes into one categorised stream."),
  html.Div([html.Button("CLEAR LOGS",id="clear-logs",className="ghost"),
            html.A("DOWNLOAD TXT",id="log-dl",href=data_uri("text/plain",text),download="ks5692_logs.txt",className="download")],
           className="actions"),
  html.Pre(text or "No logs",id="log-out",className="terminal tall"),
 ],className="page")

@lru_cache(maxsize=1)
def comparison_figure():
 metrics=["Bandwidth Mbps","Throughput Mbps","Critical Delivery %"]
 return {"data":[
  {"type":"bar","name":"CAN","x":metrics,"y":[1,.7,91],"marker":{"color":"#5a6884"}},
  {"type":"bar","name":"Proposed","x":metrics,"y":[1000,850,99.8],"marker":{"color":"#6d7cff"}}],
  "layout":{"template":"plotly_dark","height":380,"autosize":True,"barmode":"group","bargap":.35,
   "paper_bgcolor":"rgba(0,0,0,0)","plot_bgcolor":"rgba(0,0,0,0)","font":{"color":"#a9b7cc"},
   "margin":{"l":35,"r":15,"t":45,"b":40},"uirevision":"comparison",
   "legend":{"orientation":"h","y":1.02,"x":1,"xanchor":"right","yanchor":"bottom"},
   "xaxis":{"gridcolor":"rgba(140,165,205,.10)","zeroline":False,"automargin":True},
   "yaxis":{"gridcolor":"rgba(140,165,205,.10)","zeroline":False,"automargin":True}}}

def page_comparison():
 rows=[{"Parameter":a,"Conventional CAN":b,"Proposed":c} for a,b,c in
       [("Bandwidth","Low","High"),("ADAS Support","Limited","Supported"),("Real-Time Scheduling","Limited","TSN"),
        ("Encryption","Limited","Security Layer"),("Cloud Connectivity","Limited","OCPP"),("EV Charging","No","Yes")]]
 grid=table("compare-table",["Parameter","Conventional CAN","Proposed"],rows); grid.page_size=10
 return html.Div([
  head("Baseline","Performance Comparison","Reference figures quoted for the report."),
  html.Div("Simulated comparison data — not measured physical-network results.",className="warning"),
  grid,
  dcc.Graph(id="compare-graph",figure=comparison_figure(),config={"displayModeBar":False,"responsive":True,"displaylogo":False},
            responsive=True,className="chart"),
 ],className="page")

def page_report():
 text=json.dumps(snapshot(),indent=2)
 return html.Div([
  head("Export","Simulation Report","A JSON snapshot of the current run, refreshed live."),
  html.A("DOWNLOAD JSON",id="rep-dl",href=data_uri("application/json",text),download="ks5692_report.json",className="download"),
  html.Pre(text,id="rep-out",className="terminal tall"),
 ],className="page")

RENDER={"Overview":page_overview,"Live Vehicle":page_vehicle,"CAN XL":page_can,"Gateway":page_gateway,"Ethernet":page_ethernet,
        "TSN":page_tsn,"Performance":page_performance,"Security":page_security,"EV Charging":page_charging,
        "OCPP & CSMS":page_ocpp,"Logs":page_logs,"Comparison":page_comparison,"Reports":page_report}

# ----------------------------------------------------------------- rendering
# The page skeleton is built only when the page changes; the clock then updates
# just the dynamic slots inside it, so CSS animations are never remounted and
# scroll position, table paging and text selection all survive a tick.
@app.callback(Output("content","children"),Input("page","value"))
def render(page):
 with lock: return RENDER[page]()

@app.callback(Output("status","className"),Output("status-text","children"),Output("meta-run","children"),
              Output("meta-tick","children"),Output("start","disabled"),Output("pause","disabled"),
              Output("resume","disabled"),Output("stop","disabled"),Input("clock","n_intervals"))
def header_tick(_):
 with lock:
  running,paused=sim.running,sim.paused
  state="paused" if paused else "live" if running else "offline"
  return (f"status {state}",state.upper(),sim.run_id,f"{sim.tick_count:,}",
          running,(not running) or paused,(not running) or (not paused),not running)

# ------------------------------------------------------------- per-page ticks
@app.callback(*[Output(f"node-{i}","className") for i in range(len(NODES))],
              *[Output(f"nodestat-{i}","children") for i in range(len(NODES))],
              Output("topo","className"),Output("ov-kpis","children"),Output("ov-current","children"),
              Input("clock","n_intervals"))
def overview_tick(_):
 with lock: st=ov_state()
 return (*st["classes"],*st["states"],st["topo"],[kpi(*x) for x in st["cards"]],st["current"])

@app.callback(Output("g-speed","style"),Output("g-speed-v","children"),Output("g-soc","style"),Output("g-soc-v","children"),
              Output("g-rpm","style"),Output("g-rpm-v","children"),Output("m-btemp","style"),Output("m-btemp-v","children"),
              Output("m-mtemp","style"),Output("m-mtemp-v","children"),Output("m-adas","style"),Output("m-adas-v","children"),
              Output("m-torque","style"),Output("m-torque-v","children"),Output("veh-kpis","children"),
              Input("clock","n_intervals"))
def vehicle_tick(_):
 with lock: st=veh_state()
 values=[]
 for pct,text in st["rings"]: values+=[{"--p":f"{pct:.1f}"},text]
 for pct,text in st["meters"]: values+=[{"--w":f"{pct:.1f}%"},text]
 return (*values,[kpi(*x) for x in st["cards"]])

@app.callback(Output("can-kpis","children"),Output("can-table","data"),Output("can-bus","className"),Input("clock","n_intervals"))
def can_tick(_):
 with lock: st=can_state()
 return [kpi(*x) for x in st["cards"]],st["rows"],st["pipe"]

@app.callback(Output("gw-kpis","children"),Output("gw-table","data"),Output("gw-pipe","className"),Input("clock","n_intervals"))
def gateway_tick(_):
 with lock: st=gw_state()
 return [kpi(*x) for x in st["cards"]],st["rows"],st["pipe"]

@app.callback(Output("eth-kpis","children"),Output("eth-fill","style"),Output("eth-util","children"),
              Output("eth-state","children"),Output("eth-panel","className"),Input("clock","n_intervals"))
def ethernet_tick(_):
 with lock: st=eth_state()
 return [kpi(*x) for x in st["cards"]],{"--w":f'{st["util"]:.1f}%'},st["label"],st["state"],st["panel"]

@app.callback(Output("tsn-kpis","children"),Output("tsn-active","children"),Input("clock","n_intervals"))
def tsn_tick(_):
 with lock: st=tsn_state()
 return [kpi(*x) for x in st["cards"]],st["active"]

@app.callback(Output("perf-kpis","children"),Input("clock","n_intervals"))
def performance_tick(_):
 with lock: st=perf_state()
 return [kpi(*x) for x in st["cards"]]

@app.callback(Output("sec-kpis","children"),Output("sec-radar","className"),Output("sec-verdict","children"),
              Output("sec-log","children"),Input("clock","n_intervals"))
def security_tick(_):
 with lock: st=sec_state()
 return [kpi(*x) for x in st["cards"]],st["radar"],st["verdict"],st["log"]

@app.callback(Output("ev-kpis","children"),Output("ev-fill","style"),Output("ev-soc-label","children"),
              Output("ev-rig","className"),Input("clock","n_intervals"))
def charging_tick(_):
 with lock: st=ev_state()
 return [kpi(*x) for x in st["cards"]],{"--w":f'{st["soc"]:.1f}%'},st["label"],st["rig"]

@app.callback(Output("ocpp-kpis","children"),Output("ocpp-link","className"),Output("ocpp-log","children"),
              Output("sync","disabled"),Input("clock","n_intervals"))
def ocpp_tick(_):
 with lock: st=ocpp_state()
 return [kpi(*x) for x in st["cards"]],st["ws"],st["log"],st["sync_disabled"]

@app.callback(Output("log-out","children"),Output("log-dl","href"),Input("clock","n_intervals"))
def logs_tick(_):
 with lock: text=logs_text()
 return text or "No logs",data_uri("text/plain",text)

@app.callback(Output("rep-out","children"),Output("rep-dl","href"),Input("clock","n_intervals"))
def report_tick(_):
 with lock: text=json.dumps(snapshot(),indent=2)
 return text,data_uri("application/json",text)

# ------------------------------------------------------------------ controls
@app.callback(Output("sink-controls","data"),Input("start","n_clicks"),Input("pause","n_clicks"),Input("resume","n_clicks"),
              Input("stop","n_clicks"),Input("reset","n_clicks"),Input("mode","value"),Input("capacity","value"),
              Input("speed","value"),prevent_initial_call=True)
def controls(*v):
 with lock:
  t=ctx.triggered_id
  if t=="start" and not sim.running:
   sim.start()
   engine.db.execute("INSERT OR REPLACE INTO simulation_runs VALUES(?,?,?,?,?)",
                     (sim.run_id,time.strftime("%Y-%m-%dT%H:%M:%S"),None,sim.mode,sim.capacity))
   engine.boot(sim); sim.log("SYSTEM","Started")
  elif t=="pause" and sim.running: sim.paused=True; sim.log("SYSTEM","Paused")
  elif t=="resume" and sim.running: sim.paused=False; sim.log("SYSTEM","Resumed")
  elif t=="stop" and sim.running: sim.stop(); sim.log("SYSTEM","Stopped")
  elif t=="reset": sim.reset()
  elif t=="mode": sim.mode=v[5]
  elif t=="capacity": sim.capacity=int(v[6])
  elif t=="speed": sim.speed_factor=float(v[7])
 return {"event":t,"time":time.time()}

@app.callback(Output("sink-attacks","data"),Input("replay","n_clicks"),Input("unauthorized","n_clicks"),
              Input("modified","n_clicks"),Input("clear-alerts","n_clicks"),prevent_initial_call=True)
def attacks(*_):
 with lock:
  kinds={"replay":"Replay","unauthorized":"Unauthorized","modified":"Modified"}
  if ctx.triggered_id in kinds: engine.inject(sim,kinds[ctx.triggered_id])
  else: sim.security_events.clear()
 return time.time()

# Keep every Input of a callback on one page: Dash skips a callback whose
# inputs are not all present in the current layout, so mixing the EV Charging
# buttons with the OCPP page's "sync" button silently disables both.
@app.callback(Output("sink-charge","data"),Input("connect","n_clicks"),Input("authorize","n_clicks"),
              Input("charge","n_clicks"),Input("stop-charge","n_clicks"),Input("disconnect","n_clicks"),
              prevent_initial_call=True)
def charge_actions(*_):
 with lock:
  t=ctx.triggered_id; c=sim.charger
  if t=="connect": c.connect(); engine.ocpp_send(sim,"StatusNotification",{"status":"Occupied"})
  elif t=="authorize" and c.authorize(): engine.ocpp_send(sim,"Authorize",{"idToken":"DEMO-RFID-001"})
  elif t=="charge" and c.start(): engine.ocpp_send(sim,"TransactionEvent",{"eventType":"Started","transactionId":c.transaction_id})
  elif t=="stop-charge" and c.stop(): engine.ocpp_send(sim,"TransactionEvent",{"eventType":"Ended","transactionId":c.transaction_id})
  elif t=="disconnect": c.disconnect(); engine.ocpp_send(sim,"StatusNotification",{"status":"Available"})
 return time.time()

@app.callback(Output("sink-sync","data"),Input("sync","n_clicks"),prevent_initial_call=True)
def sync_queue(_):
 with lock:
  queued=list(sim.unsent_ocpp); sim.unsent_ocpp.clear()
  for x in queued: engine.ocpp_send(sim,x["type"],x["payload"].get("payload",{}))
 return time.time()

@app.callback(Output("sink-logs","data"),Input("clear-logs","n_clicks"),prevent_initial_call=True)
def clear_logs(_):
 with lock: sim.logs.clear()
 return time.time()

# -------------------------------------------------------------------- charts
EMPTY_LAYOUT={"template":"plotly_dark","height":380,"autosize":True,"paper_bgcolor":"rgba(0,0,0,0)",
              "plot_bgcolor":"rgba(0,0,0,0)","font":{"color":"#a9b7cc"},"margin":{"l":35,"r":15,"t":52,"b":32},
              "uirevision":"stable","xaxis":{"visible":False},"yaxis":{"visible":False}}

def line(cols,title):
 with lock: rows=list(sim.history)[-120:]
 if not rows:
  return {"data":[],"layout":{**EMPTY_LAYOUT,"title":{"text":title,"x":.02,"font":{"size":14}},
          "annotations":[{"text":"Start the simulation to populate live data","xref":"paper","yref":"paper","x":.5,"y":.5,
                          "showarrow":False,"font":{"color":"#6d7d96","size":13}}]}}
 colors=["#6d7cff","#2ee6c8","#ffb454","#b98bff"]
 times=[row.get("time","") for row in rows]
 traces=[{"type":"scatter","mode":"lines","name":column,"x":times,
          "y":[row.get(column,0) for row in rows],
          "line":{"color":colors[i%len(colors)],"width":2.2,"shape":"spline","smoothing":.55},
          "hovertemplate":f"{column}: %{{y:.2f}}<extra></extra>"} for i,column in enumerate(cols)]
 layout={"template":"plotly_dark","height":380,"autosize":True,"paper_bgcolor":"rgba(0,0,0,0)",
         "plot_bgcolor":"rgba(0,0,0,0)","font":{"color":"#a9b7cc"},"title":{"text":title,"x":.02,"font":{"size":14}},
         "margin":{"l":35,"r":15,"t":52,"b":32},"uirevision":"stable","hovermode":"x unified",
         "legend":{"orientation":"h","y":1.02,"x":1,"xanchor":"right","yanchor":"bottom"},
         "xaxis":{"gridcolor":"rgba(140,165,205,.10)","zeroline":False,"automargin":True,"title":""},
         "yaxis":{"gridcolor":"rgba(140,165,205,.10)","zeroline":False,"automargin":True,"title":""}}
 return {"data":traces,"layout":layout}

@app.callback(Output("vehicle-a","figure"),Output("vehicle-b","figure"),Input("clock","n_intervals"))
def vg(_): return line(["speed","rpm"],"Speed and RPM"),line(["soc","battery_temp","adas"],"SOC, Temperature, ADAS")
@app.callback(Output("ethernet-graph","figure"),Input("clock","n_intervals"))
def eg(_): return line(["throughput","utilization"],"Bandwidth and Utilisation")
@app.callback(Output("latency-graph","figure"),Output("throughput-graph","figure"),Input("clock","n_intervals"))
def pg(_):
 return line(["latency","jitter"],"Latency and Jitter"),line(["throughput","packet_loss","utilization"],"Throughput, Loss, Utilisation")
@app.callback(Output("soc-graph","figure"),Output("power-graph","figure"),Input("clock","n_intervals"))
def cg(_): return line(["soc"],"Battery state of charge"),line(["voltage","current"],"Voltage and Current")

if __name__=="__main__": app.run(debug=False,host="127.0.0.1",port=8050)
