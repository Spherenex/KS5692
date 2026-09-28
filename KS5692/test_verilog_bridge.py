import unittest

from state_manager import SimulationState
from verilog_bridge import VerilogSimulationBridge


class VerilogBridgeTests(unittest.TestCase):
    def test_rtl_values_are_mapped_to_dashboard_state(self):
        state = SimulationState()
        values = [
            4250, 77996, 3800, 0, 3820, 409, 320, 2210, 548, 950,
            1200, 350, 7, 0b11101,
            100, 101, 0, 300, 102,
            230, 231, 106, 511, 232,
            100,
        ]
        tick = VerilogSimulationBridge._decode(state, values)

        self.assertEqual(state.vehicle["speed"], 42.5)
        self.assertAlmostEqual(state.vehicle["soc"], 77.996)
        self.assertEqual([ecu.ecu_name for ecu in tick.ecus], ["BMS", "MCU", "VCU", "ADAS", "CCU"])
        self.assertTrue(tick.decisions["BMS"].delivered)
        self.assertFalse(tick.decisions["MCU"].delivered)
        self.assertAlmostEqual(tick.decisions["ADAS"].latency_ms, .511)

    def test_missing_toolchain_uses_compatibility_mode(self):
        bridge = VerilogSimulationBridge(strict=False)
        bridge.iverilog = None
        bridge.vvp = None

        self.assertFalse(bridge.prepare())
        self.assertIn("not found", bridge.last_error)
        self.assertEqual(bridge.backend_name, "Python compatibility")


if __name__ == "__main__":
    unittest.main()
