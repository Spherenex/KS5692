# Design and Implementation of a Composite and Secure Connection Ethernet Network for Next Generation Automotive and Automation System with OCPP Integration

KS5692 is a Dash/Plotly browser-based Python demonstration of virtual automotive ECUs, CAN XL-style frames, a secure CAN/Ethernet gateway, Automotive Ethernet, TSN scheduling, attack detection, EV charging, OCPP 2.0.1-style messages, a CSMS, monitoring, SQLite persistence, and reports.

## Requirements and installation

Python 3.10+ is required.

```powershell
python -m venv venv
venv\Scripts\activate
python -m pip install -r requirements.txt
python dashboard.py
```

Alternatively, double-click `run_dashboard.bat`, then open
`http://127.0.0.1:8050` in a browser.

## Dashboard pages

System Overview shows the complete live architecture. Live Vehicle visualizes ECU telemetry. CAN XL Monitor shows authenticated software frames. Gateway shows conversion. Automotive Ethernet presents bandwidth and loss. TSN Scheduler displays 802.1Qbv-inspired priority windows. Network Performance charts latency, jitter, throughput, loss, and utilization. Security Center injects safe local attacks. EV Charging controls a virtual charge session. OCPP & CSMS shows structured messages and offline synchronization. Communication Logs provides filtering and downloads. Performance Comparison uses explicitly simulated figures. Reports exports a run summary.

## Simulation modes

- Normal: ordinary integrated operation.
- High Traffic: raises ADAS traffic toward 700 Mbps.
- Cyberattack: periodically injects replay, unauthorized, and modified messages.
- Network Failure: stops Ethernet delivery and records losses.
- OCPP Connection Failure: charging continues locally while messages queue for later synchronization.

## Architecture

```text
ECUs → CAN XL → Security → Gateway → TSN → Automotive Ethernet
                                                ↓
                                         EV Charger → OCPP → CSMS
```

## Important disclaimer

CAN XL, Automotive Ethernet, TSN, SecOC, MACsec, and OCPP behavior in this project is demonstrated through a Python software simulation. It is not certification-level, standards-conformity, safety validation, penetration-testing, or physical protocol validation software.
