import base64
import json
import unittest

import dashboard


class StudioToolbarTests(unittest.TestCase):
    def setUp(self):
        with dashboard.lock:
            dashboard.sim.reset()
        self.client = dashboard.server.test_client()

    def control(self, changed):
        ids = ["start", "pause", "resume", "stop", "reset", "mode", "capacity", "speed",
               "new-project", "step", "validate-rtl"]
        properties = ["n_clicks"] * 5 + ["value"] * 3 + ["n_clicks"] * 3
        values = [None, None, None, None, None, "Normal Mode", 1000, 1, None, None, None]
        values[ids.index(changed)] = 1 if properties[ids.index(changed)] == "n_clicks" else values[ids.index(changed)]
        return self.client.post("/_dash-update-component", json={
            "output": "sink-controls.data",
            "outputs": {"id": "sink-controls", "property": "data"},
            "inputs": [{"id": name, "property": prop, "value": value}
                       for name, prop, value in zip(ids, properties, values)],
            "state": [], "changedPropIds": [f"{changed}.{properties[ids.index(changed)]}"],
        })

    def test_validate_step_resume_pause_and_reset(self):
        self.assertEqual(self.control("validate-rtl").status_code, 200)
        self.assertTrue(dashboard.engine.verilog._ready)

        self.assertEqual(self.control("step").status_code, 200)
        self.assertEqual(dashboard.sim.tick_count, 1)
        self.assertTrue(dashboard.sim.paused)
        self.assertEqual(dashboard.engine.verilog.backend_name, "SystemVerilog (Icarus)")

        self.assertEqual(self.control("resume").status_code, 200)
        self.assertFalse(dashboard.sim.paused)
        self.assertEqual(self.control("pause").status_code, 200)
        self.assertTrue(dashboard.sim.paused)
        self.assertEqual(self.control("reset").status_code, 200)
        self.assertEqual(dashboard.sim.tick_count, 0)

    def test_save_export_report_and_open_project(self):
        for output, component, trigger in [
            ("project-download.data", "project-download", "save-project"),
            ("export-download.data", "export-download", "export-run"),
            ("page.value", "page", "show-report"),
        ]:
            response = self.client.post("/_dash-update-component", json={
                "output": output, "outputs": {"id": component, "property": output.split(".")[-1]},
                "inputs": [{"id": trigger, "property": "n_clicks", "value": 1}],
                "state": [], "changedPropIds": [f"{trigger}.n_clicks"],
            })
            self.assertEqual(response.status_code, 200, trigger)

        project = dashboard.project_payload()
        encoded = "data:application/json;base64," + base64.b64encode(json.dumps(project).encode()).decode()
        output = next(key for key in dashboard.app.callback_map if key.startswith("..mode.value"))
        response = self.client.post("/_dash-update-component", json={
            "output": output,
            "outputs": [{"id":"mode","property":"value"},{"id":"capacity","property":"value"},
                        {"id":"speed","property":"value"},{"id":"sink-open","property":"data"}],
            "inputs": [{"id":"new-project","property":"n_clicks","value":None},
                       {"id":"open-project","property":"contents","value":encoded}],
            "state": [{"id":"open-project","property":"filename","value":"project.json"},
                      {"id":"mode","property":"value","value":"Normal Mode"},
                      {"id":"capacity","property":"value","value":1000},
                      {"id":"speed","property":"value","value":1}],
            "changedPropIds": ["open-project.contents"],
        })
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
