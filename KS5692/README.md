# Design and Implementation of a Composite and Secure Connection Ethernet Network for Next Generation Automotive and Automation System with OCPP Integration

KS5692 is a Dash/Plotly browser application backed by a SystemVerilog vehicle and network simulation. The RTL model drives virtual automotive ECUs, CAN XL traffic inputs, TSN gate timing, congestion, and Ethernet delivery. Python hosts the unchanged dashboard and application-layer integrations: security, EV charging, OCPP 2.0.1 WebSockets, CSMS, SQLite persistence, and reports.

## Requirements and installation

Python 3.10+ and Icarus Verilog are required for the RTL backend. The bridge
uses the project-local `.tools/iverilog` installation when present, otherwise
it looks for `iverilog` and `vvp` on `PATH`.

```powershell
python -m venv venv
venv\Scripts\activate
python -m pip install -r requirements.txt
python dashboard.py
```

At the first simulation tick the bridge compiles `rtl/automotive_sim.sv` and
`rtl/automotive_tb.sv` into `data/verilog/automotive_sim.vvp`. Later runs reuse
the compiled file until an RTL source changes. To require RTL and stop instead
of using the compatibility model when Icarus is missing, set:

```powershell
$env:KS5692_REQUIRE_VERILOG="1"
python dashboard.py
```

Optional `IVERILOG` and `VVP` environment variables may contain explicit paths
to the two executables. The browser uses a desktop-style Verilog Simulation
Studio layout, and its console records the active simulation backend.

## Simulation Studio toolbar

- **New** resets the run and restores the default project configuration.
- **Open / Save** load and download a project JSON containing configuration and RTL sources.
- **Validate** forces SystemVerilog compilation and elaboration.
- **Run / Pause / Resume / Stop / Reset** control continuous execution.
- **Step** executes exactly one RTL tick and returns to the paused state.
- **Export** downloads the current run snapshot; **Report** opens the live report tab.

Alternatively, double-click `run_dashboard.bat`, then open
`http://127.0.0.1:8050` in a browser.

## Dashboard pages

System Overview shows the complete live architecture. Live Vehicle visualizes ECU telemetry. CAN XL Monitor shows authenticated software frames. Gateway shows authenticated and AES-GCM-encrypted Ethernet conversion. Automotive Ethernet presents bandwidth, recovery, and loss. TSN Scheduler displays 802.1Qbv-inspired priority windows and gate waits. Network Performance charts latency, jitter, throughput, loss, and utilization. Security Center injects safe local attacks. EV Charging controls a virtual charge session. OCPP & CSMS shows WebSocket CALL/CALLRESULT messages and offline synchronization. Communication Logs provides filtering and downloads. Performance Comparison uses explicitly simulated figures. Reports exports a run summary.

## Simulation modes

- Normal: ordinary integrated operation.
- High Traffic: raises ADAS traffic toward 700 Mbps.
- Cyberattack: periodically injects replay, unauthorized, and modified messages.
- Network Failure: stops Ethernet delivery and records losses.
- OCPP Connection Failure: charging continues locally while messages queue for synchronization after the WebSocket returns.

## Integrated security and protocol behavior

- CAN messages use an HMAC-SHA256 authentication tag, a sequence counter, source authorization, and CAN-ID/source validation.
- Ethernet payloads use AES-256-GCM as a software representation of MACsec confidentiality and integrity principles.
- TSN scheduling uses numerical gate windows and priority queues; its wait and transmission times feed the end-to-end latency measurement.
- The local CSMS listens on `ws://127.0.0.1:9010` with the `ocpp2.0.1` WebSocket subprotocol. The implemented educational subset includes BootNotification, Authorize, StatusNotification, TransactionEvent, and MeterValues.
- SQLite stores run, vehicle, network, security, charging-session, and OCPP records.

## Architecture

```text
ECUs → CAN XL → Security → Gateway → TSN → Automotive Ethernet
                                                ↓
                                         EV Charger → OCPP → CSMS
```

## Important disclaimer

CAN XL, Automotive Ethernet, TSN, SecOC, MACsec, and OCPP behavior in this project is an educational mixed RTL/application simulation. Although it uses a real SystemVerilog timing model, local WebSocket transport, and valid OCPP request/response framing for the implemented messages, it is not a complete OCPP certification stack, certification-level standards-conformity test, safety validation, penetration-testing tool, or physical protocol validation system.
