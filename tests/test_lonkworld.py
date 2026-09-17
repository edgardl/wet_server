"""Integration contract through WET's real script loader and Flask routing."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("wet_test_app", ROOT / "docker" / "app.py")
host = importlib.util.module_from_spec(spec)
spec.loader.exec_module(host)


class LonkWorldRoutes(unittest.TestCase):
    def setUp(self):
        self.client = host.app.test_client()

    def simulate(self, **body):
        response = self.client.post("/lonkworld", data=json.dumps(body), content_type="application/json")
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()["data"]

    def test_page_and_fresh_json(self):
        page = self.client.get("/lonkworld")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"Talk to", page.data)
        self.assertIn(b"localStorage", page.data)
        self.assertEqual(self.client.get("/lonkworld?format=json").get_json()["data"]["tick"], 0)

    def test_determinism_continuation_and_isolation(self):
        first = self.simulate(seed=81, steps=2)
        self.assertEqual(first["world"], self.simulate(seed=81, steps=2)["world"])
        continued = self.simulate(world=first["world"], steps=3)
        self.assertEqual(continued["tick"], 5)
        self.assertEqual(continued["world"], self.simulate(seed=81, steps=5)["world"])
        self.assertTrue(any(l["social"]["graduated_at"] is not None for l in continued["world"]["lonks"]))
        self.assertEqual(self.simulate(seed=81)["tick"], 0)

    def test_talking_survives_restore_and_has_learning_stages(self):
        first = self.simulate(seed=81)
        uid = first["world"]["lonks"][0]["uid"]
        spoken = self.simulate(world=first["world"], message="sparkle flibber moon", target_uid=uid)
        restored = self.simulate(world=spoken["world"])
        lonk = next(l for l in restored["world"]["lonks"] if l["uid"] == uid)
        self.assertIn("sparkle", lonk["linguistics"]["tokens"])
        self.assertTrue(any("sparkle flibber moon" in e["text"] for e in lonk["memory"]["player_interactions"]))
        self.assertIn("stage", lonk["social"])
        self.assertIn("graduated_at", lonk["social"])

    def test_rejects_unbounded_and_invalid_inputs(self):
        for body in ({"steps": 6}, {"steps": -1}, {"steps": True}, {"steps": 1.2},
                     {"seed": False}, {"message": "x" * 501}, {"target_uid": 1},
                     {"world": None}, {"target_uid": "not-a-lonk"}):
            with self.subTest(body=body):
                self.assertEqual(self.client.post("/lonkworld", json=body).status_code, 400)
        self.assertEqual(self.client.post("/lonkworld", data="{broken").status_code, 400)
        self.assertEqual(self.client.post("/lonkworld", json=[]).status_code, 400)
        self.assertEqual(self.client.post("/lonkworld", data=" " * (2 * 1024 * 1024 + 1)).status_code, 413)
        self.assertEqual(self.client.delete("/lonkworld").status_code, 405)

    def test_opaque_state_preserves_numeric_word_order(self):
        taught = self.simulate(seed=81, message="moon 123 sparkle 2")
        self.assertEqual(list(taught["world"]["lonks"][0]["linguistics"]["tokens"]),
                         ["moon", "123", "sparkle", "2"])
        # Even transports sorting the enclosing response cannot reorder keys
        # inside the authoritative JSON string (JavaScript orders numeric keys).
        transported = json.loads(json.dumps(taught, sort_keys=True))["world_json"]
        self.assertEqual(self.simulate(world_json=transported)["world"], taught["world"])
        continued = self.simulate(world_json=transported, steps=2)
        direct = self.simulate(seed=81, message="moon 123 sparkle 2", steps=2)
        self.assertEqual(continued["world_json"], direct["world_json"])
        self.assertEqual(continued["world"]["rng_state"], direct["world"]["rng_state"])

    def test_rejects_changed_source_config_and_population(self):
        world = self.simulate()["world"]
        for field, value in (("source_hash", "other-version"), ("config", {}), ("max_population", 100000)):
            damaged = copy.deepcopy(world)
            damaged[field] = value
            with self.subTest(field=field):
                self.assertEqual(self.client.post("/lonkworld", json={"world": damaged}).status_code, 400)


if __name__ == "__main__":
    unittest.main()
