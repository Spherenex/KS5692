"""Host bridge for the SystemVerilog vehicle/network simulation core."""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from config import BASE_DIR
from models import ECUData


class VerilogBackendError(RuntimeError):
    pass


@dataclass(frozen=True)
class NetworkDecision:
    delivered: bool
    wait_ms: float
    latency_ms: float


@dataclass(frozen=True)
class VerilogTick:
    ecus: list[ECUData]
    decisions: dict[str, NetworkDecision]


class VerilogSimulationBridge:
    """Compile the RTL once and execute one deterministic testbench step per tick."""

    MODES = {
        "Normal Mode": 0,
        "High Traffic Mode": 1,
        "Cyberattack Mode": 2,
        "Network Failure Mode": 3,
        "OCPP Connection Failure Mode": 4,
    }

    def __init__(self, strict: bool | None = None):
        self.strict = (os.getenv("KS5692_REQUIRE_VERILOG", "0") == "1") if strict is None else strict
        local_bin = BASE_DIR / ".tools" / "iverilog" / "bin"
        local_iverilog = local_bin / "iverilog.exe"
        local_vvp = local_bin / "vvp.exe"
        self.iverilog = os.getenv("IVERILOG") or shutil.which("iverilog") or (str(local_iverilog) if local_iverilog.exists() else None)
        self.vvp = os.getenv("VVP") or shutil.which("vvp") or (str(local_vvp) if local_vvp.exists() else None)
        self.rtl_dir = BASE_DIR / "rtl"
        self.build_dir = BASE_DIR / "data" / "verilog"
        self.executable = self.build_dir / "automotive_sim.vvp"
        self._ready: bool | None = None
        self.last_error = ""

    @property
    def backend_name(self) -> str:
        if self._ready is True or (self._ready is None and self.iverilog and self.vvp):
            return "SystemVerilog (Icarus)"
        return "Python compatibility"

    def prepare(self, force: bool = False) -> bool:
        if force:
            self._ready = None
            self.last_error = ""
        if self._ready is not None:
            return self._ready
        if not self.iverilog or not self.vvp:
            return self._fail("Icarus Verilog was not found; install iverilog and vvp or set IVERILOG/VVP")
        sources = [self.rtl_dir / "automotive_sim.sv", self.rtl_dir / "automotive_tb.sv"]
        try:
            self.build_dir.mkdir(parents=True, exist_ok=True)
            stale = not self.executable.exists() or any(
                source.stat().st_mtime > self.executable.stat().st_mtime for source in sources
            )
            if stale:
                result = subprocess.run(
                    [self.iverilog, "-g2012", "-s", "automotive_tb", "-o", str(self.executable), *map(str, sources)],
                    cwd=BASE_DIR, capture_output=True, text=True, timeout=30, check=False,
                )
                if result.returncode:
                    return self._fail(f"RTL compilation failed: {(result.stderr or result.stdout).strip()}")
            self._ready = True
            return True
        except (OSError, subprocess.SubprocessError) as exc:
            return self._fail(f"RTL preparation failed: {exc}")

    def _fail(self, message: str) -> bool:
        self.last_error = message
        self._ready = False
        if self.strict:
            raise VerilogBackendError(message)
        return False

    def step(self, state) -> VerilogTick | None:
        if not self.prepare():
            return None
        vehicle = state.vehicle
        args = [
            self.vvp, str(self.executable),
            f"+TICK={state.tick_count}",
            f"+MODE={self.MODES.get(state.mode, 0)}",
            f"+FACTOR={round(state.speed_factor * 100)}",
            f"+CAPACITY={state.capacity}",
            f"+CHARGING={int(state.charger.status == 'Charging')}",
            f"+PARKED={int(vehicle.get('drive_mode') == 'Park')}",
            f"+SPEED={round(vehicle.get('speed', 42) * 100)}",
            f"+SOC={round(vehicle.get('soc', 78) * 1000)}",
            f"+CURRENT={round(state.charger.current * 10)}",
        ]
        try:
            result = subprocess.run(args, cwd=BASE_DIR, capture_output=True, text=True, timeout=5, check=False)
        except (OSError, subprocess.SubprocessError) as exc:
            self._fail(f"RTL execution failed: {exc}")
            return None
        if result.returncode:
            self._fail(f"RTL execution failed: {(result.stderr or result.stdout).strip()}")
            return None
        line = next((line for line in result.stdout.splitlines() if line.startswith("KS5692,")), "")
        try:
            values = [int(value) for value in line.split(",")[1:]]
            if len(values) != 25:
                raise ValueError(f"expected 25 values, received {len(values)}")
        except ValueError as exc:
            self._fail(f"Invalid RTL output ({exc}): {line!r}")
            return None
        return self._decode(state, values)

    @staticmethod
    def _decode(state, values: list[int]) -> VerilogTick:
        (speed, soc, accel, brake, voltage, current, battery_temp, rpm, motor_temp,
         torque, adas, obstacle, objects, delivered, *timing) = values
        v = state.vehicle
        charging = state.charger.status == "Charging"
        v.update(
            speed=speed / 100, soc=soc / 1000, accelerator=accel / 100,
            brake=bool(brake), drive_mode="Drive", voltage=voltage / 10,
            current=current / 10, battery_temp=battery_temp / 10, soh=96,
            rpm=rpm, motor_temp=motor_temp / 10, torque=torque / 10,
            adas=adas / 10, obstacle=obstacle / 10,
        )
        ecus = [
            ECUData("ECU-1", "BMS", parameters={"SOC":round(v["soc"],2), "Voltage":v["voltage"], "Current":v["current"], "Temperature":v["battery_temp"], "SOH":96, "Charging":charging}),
            ECUData("ECU-2", "MCU", parameters={"RPM":rpm, "Temperature":v["motor_temp"], "Torque":v["torque"], "Current":v["current"], "Status":"ACTIVE"}),
            ECUData("ECU-3", "VCU", parameters={"Speed":v["speed"], "Accelerator":v["accelerator"], "Brake":bool(brake), "DriveMode":"Drive", "Status":"READY"}),
            ECUData("ECU-4", "ADAS", parameters={"CameraMbps":round(v["adas"]*.7,1), "Objects":objects, "RadarMbps":round(v["adas"]*.2,1), "Lane":"CENTERED", "ObstacleM":v["obstacle"], "TotalMbps":v["adas"]}),
            ECUData("ECU-5", "CCU", parameters={"Request":charging, "Connector":state.charger.connector, "Voltage":round(state.charger.voltage,1), "Current":round(state.charger.current,1), "PowerKW":round(state.charger.power_kw,2), "EnergyKWh":round(state.charger.energy_kwh,3), "Status":state.charger.status}),
        ]
        waits, latencies = timing[:5], timing[5:10]
        sources = ("BMS", "MCU", "VCU", "ADAS", "CCU")
        decisions = {
            source: NetworkDecision(bool(delivered & (1 << index)), waits[index] / 1000, latencies[index] / 1000)
            for index, source in enumerate(sources)
        }
        return VerilogTick(ecus, decisions)
