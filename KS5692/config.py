from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"
DB_PATH = DATA_DIR / "simulation.db"
MAX_HISTORY = 240
MAX_LOGS = 500
TICK_SECONDS = 0.75
ECU_IDS = {"BMS": "0x101", "MCU": "0x102", "VCU": "0x103", "ADAS": "0x104", "CCU": "0x105"}
MODULES = ["Vehicle ECUs", "CAN XL", "Gateway", "Automotive Ethernet", "TSN", "Security", "EV Charger", "OCPP", "CSMS"]
for directory in (DATA_DIR, LOG_DIR):
    directory.mkdir(parents=True, exist_ok=True)

