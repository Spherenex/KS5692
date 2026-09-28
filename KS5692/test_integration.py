import socket
import sqlite3
import tempfile
import unittest
from pathlib import Path

from database import Database
from main import SimulationEngine
from state_manager import SimulationState


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class IntegratedSimulationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.temp.name) / "test.db")
        self.engine = SimulationEngine(self.db, free_port())
        self.state = SimulationState()
        self.state.start()
        self.db.execute("INSERT INTO simulation_runs VALUES(?,?,?,?,?)",
                        (self.state.run_id, "start", None, self.state.mode, self.state.capacity))

    def tearDown(self):
        self.engine.ocpp.disconnect()
        self.engine.csms.stop()
        self.temp.cleanup()

    def test_secure_network_charging_and_persistence(self):
        boot = self.engine.ocpp_send(self.state, "BootNotification", {"reason": "PowerUp"})
        self.assertEqual(boot["response"]["status"], "Accepted")
        self.assertTrue(self.engine.ocpp.connected)

        for _ in range(5):
            self.engine.tick(self.state)
        self.assertEqual(self.state.stats["can"], 25)
        self.assertGreater(self.state.stats["delivered"], 0)
        packet = self.state.packets[0]
        self.assertEqual(packet.security_status, "AUTHENTICATED + ENCRYPTED")
        payload, reason = self.engine.security.verify_ethernet(packet)
        self.assertIsInstance(payload, dict)
        self.assertEqual(reason, "MACsec integrity verified")

        for attack in ("Replay", "Unauthorized", "Modified"):
            self.engine.inject(self.state, attack)
        reasons = {event["type"]: event["reason"] for event in self.state.security_events}
        self.assertEqual(reasons["Replay"], "Replay detected")
        self.assertEqual(reasons["Unauthorized"], "Unauthorized source")
        self.assertEqual(reasons["Modified"], "Integrity failure")

        charger = self.state.charger
        charger.connect(); self.assertTrue(charger.authorize()); self.assertTrue(charger.start(self.state.vehicle["soc"]))
        self.engine.tick(self.state)
        self.assertAlmostEqual(charger.power_kw, 19.296, places=3)
        self.assertTrue(charger.stop(self.state.vehicle["soc"]))
        self.engine.record_charging_session(self.state)

        with sqlite3.connect(self.db.path) as connection:
            self.assertGreater(connection.execute("SELECT count(*) FROM vehicle_metrics").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT count(*) FROM security_events").fetchone()[0], 3)
            self.assertEqual(connection.execute("SELECT count(*) FROM charging_sessions").fetchone()[0], 1)
            self.assertGreater(connection.execute("SELECT count(*) FROM ocpp_messages").fetchone()[0], 0)

    def test_failure_recovery_and_offline_sync(self):
        self.engine.boot(self.state)
        self.state.mode = "Network Failure Mode"
        self.engine.tick(self.state)
        self.assertGreater(self.state.stats["dropped"], 0)
        self.assertIsNotNone(self.state.network_failure_started)
        self.state.mode = "Normal Mode"
        self.engine.tick(self.state)
        self.assertGreater(self.state.last_recovery_ms, 0)

        self.state.mode = "OCPP Connection Failure Mode"
        self.engine.ocpp_send(self.state, "MeterValues", {"test": 1})
        self.assertEqual(len(self.state.unsent_ocpp), 1)
        self.state.mode = "Normal Mode"
        self.assertEqual(self.engine.sync_ocpp_queue(self.state), 1)
        self.assertEqual(len(self.state.unsent_ocpp), 0)

        _, rejected = self.engine.ocpp.call("Authorize", {"idToken": {"idToken": "INVALID", "type": "ISO14443"}})
        self.assertEqual(rejected["status"], "Invalid")


if __name__ == "__main__":
    unittest.main()
