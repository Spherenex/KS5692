import math, random, time
from models import ECUData, now_iso

class ECUSimulator:
    def __init__(self): self.phase = 0.0
    def update(self, state):
        self.phase += .12 * state.speed_factor
        charging = state.charger.status == "Charging"
        accel = max(0.0, min(100.0, 38 + 28*math.sin(self.phase/3)))
        brake = math.sin(self.phase/5) < -.82
        speed = 0 if state.vehicle.get("drive_mode") == "Park" else max(0, state.vehicle.get("speed", 42) + accel*.018 - (2.7 if brake else .45))
        speed = min(145, speed)
        soc = min(100, max(5, state.vehicle.get("soc", 78) + (.025 if charging else -.004)))
        adas = 700 + random.uniform(-25,25) if state.mode == "High Traffic Mode" else 120 + 14*math.sin(self.phase)
        state.vehicle.update(speed=speed, accelerator=accel, brake=brake, drive_mode="Drive", soc=soc,
            voltage=382+6*math.sin(self.phase/4), current=(state.charger.current if charging else 20+accel*.55),
            battery_temp=32+2*math.sin(self.phase/7), soh=96, rpm=speed*52,
            motor_temp=48+speed*.16, torque=accel*2.5, adas=adas, obstacle=max(4, 35+22*math.sin(self.phase/2)))
        v=state.vehicle
        return [
            ECUData("ECU-1","BMS",parameters={"SOC":round(soc,2),"Voltage":round(v["voltage"],1),"Current":round(v["current"],1),"Temperature":round(v["battery_temp"],1),"SOH":96,"Charging":charging}),
            ECUData("ECU-2","MCU",parameters={"RPM":round(v["rpm"]),"Temperature":round(v["motor_temp"],1),"Torque":round(v["torque"],1),"Current":round(v["current"],1),"Status":"ACTIVE"}),
            ECUData("ECU-3","VCU",parameters={"Speed":round(speed,1),"Accelerator":round(accel,1),"Brake":brake,"DriveMode":"Drive","Status":"READY"}),
            ECUData("ECU-4","ADAS",parameters={"CameraMbps":round(adas*.7,1),"Objects":random.randint(2,12),"RadarMbps":round(adas*.2,1),"Lane":"CENTERED","ObstacleM":round(v["obstacle"],1),"TotalMbps":round(adas,1)}),
            ECUData("ECU-5","CCU",parameters={"Request":charging,"Connector":state.charger.connector,"Voltage":round(state.charger.voltage,1),"Current":round(state.charger.current,1),"PowerKW":round(state.charger.power_kw,2),"EnergyKWh":round(state.charger.energy_kwh,3),"Status":state.charger.status})]

