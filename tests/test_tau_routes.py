import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("wet_tau_test_host", ROOT / "docker/app.py")
host = importlib.util.module_from_spec(spec)
spec.loader.exec_module(host)

class TauRoutes(unittest.TestCase):
    def setUp(self):
        self.client = host.app.test_client()
        self.state = dict(version=1, phase=1, dt=0.25,
            nodes=[dict(id="a", energy=10, capacity=8, x=200, y=200),
                   dict(id="b", energy=0, capacity=8, x=400, y=300)],
            edges=[dict(source="a", target="b", weight=1)])

    def test_page_and_aliases(self):
        for path in ("/tau", "/tau/", "/tau.py"):
            page = self.client.get(path)
            self.assertEqual(page.status_code, 200)
            self.assertIn(b"fetch(location.pathname,", page.data)
            self.assertNotIn(b'src="/app.js"', page.data)

    def test_diffusion_raw_contract_and_isolation(self):
        body = dict(action="step", state=self.state)
        for _ in range(2):
            result = self.client.post("/tau", json=body)
            self.assertEqual(result.status_code, 200)
            data = result.get_json()
            self.assertEqual([n["energy"] for n in data["state"]["nodes"]], [7.5, 2.5])
            self.assertEqual(data["total"], 10)

    def test_invalid_inputs(self):
        self.assertEqual(self.client.post("/tau", json={}).status_code, 400)
        self.assertEqual(self.client.post("/tau", data="{", content_type="application/json").status_code, 400)
        self.assertEqual(self.client.post("/tau", data="x").status_code, 415)
        self.assertEqual(self.client.put("/tau", json={}).status_code, 405)
        self.assertEqual(self.client.post("/tau", data="x"*1000001, content_type="application/json").status_code, 413)
        self.state["dt"] = 2
        self.assertEqual(self.client.post("/tau", json=dict(action="step", state=self.state)).status_code, 400)
