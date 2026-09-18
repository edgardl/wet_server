import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'docker/scripts/tau'))
import math
import random
import unittest

from tau_model import diffuse, harmony


class ContractTests(unittest.TestCase):
    def test_analytic_diffusion_and_immutable_input(self):
        x = [10.0, 0.0]
        self.assertEqual(diffuse(x, [(0, 1, 1.0)], 0.25), [7.5, 2.5])
        self.assertEqual(x, [10.0, 0.0])

    def test_boundary_and_isolated_nodes(self):
        self.assertEqual(diffuse([10, 0, 3], [(0, 1, 1)], 1), [0, 10, 3])
        self.assertEqual(diffuse([10, 0], [], 1), [10, 0])

    def test_bad_graphs_and_steps(self):
        for edges, dt in [([(0, 1, -1)], 1), ([(0, 1, 1)], 1.01),
                          ([(0, 1, 1), (1, 0, 1)], 0.1),
                          ([(0, 0, 1)], 0.1), ([(0, 2, 1)], 0.1),
                          ([], -1), ([], math.nan)]:
            with self.subTest(edges=edges, dt=dt), self.assertRaises(ValueError):
                diffuse([1, 0], edges, dt)

    def test_nonfinite_and_negative_energy(self):
        for value in [math.nan, math.inf, -math.inf, -1]:
            with self.assertRaises(ValueError):
                diffuse([value, 0], [], 0)
        with self.assertRaises(ValueError):
            harmony([math.inf], [1], 1)

    def test_projection_analytic(self):
        self.assertEqual(harmony([3, -1], [2, 2], 2), [2, 0])
        actual = harmony([0, 0, 0], [1, 4, 4], 5)
        for a, b in zip(actual, [1, 2, 2]):
            self.assertAlmostEqual(a, b)

    def test_projection_feasible_identity_and_endpoints(self):
        self.assertEqual(harmony([1, 2], [3, 3], 3), [1, 2])
        self.assertEqual(harmony([10, -10], [0, 0], 0), [0, 0])
        self.assertEqual(harmony([10, -10], [2, 3], 5), [2, 3])

    def test_invalid_capacity_budget_shape(self):
        for x, c, budget in [([0], [1], 2), ([0], [-1], 0),
                             ([0], [1], -1), ([0], [1], math.nan),
                             ([0], [], 0), ([], [], 0)]:
            with self.subTest(x=x, c=c, budget=budget), self.assertRaises(ValueError):
                harmony(x, c, budget)

    def test_seeded_projection_optimality(self):
        rng = random.Random(401)
        for _ in range(100):
            x = [rng.uniform(-5, 5) for _ in range(10)]
            c = [rng.uniform(0.1, 3) for _ in x]
            budget = rng.uniform(0.1, 0.9) * math.fsum(c)
            y = harmony(x, c, budget)
            self.assertAlmostEqual(math.fsum(y), budget, places=10)
            self.assertTrue(all(0 <= a <= b for a, b in zip(y, c)))
            # First-order optimality against independent feasible competitors.
            for _ in range(10):
                z = y.copy()
                i, j = rng.sample(range(10), 2)
                transfer = min(z[i], c[j] - z[j]) * rng.random()
                z[i] -= transfer
                z[j] += transfer
                dot = math.fsum((a-b)*(d-b) for a,b,d in zip(x,y,z))
                self.assertLessEqual(dot, 1e-9)

    def test_large_finite_scale(self):
        for scale in [1e-200, 1e200]:
            result = harmony([3*scale, -scale], [2*scale, 2*scale], 2*scale)
            self.assertAlmostEqual(math.fsum(result)/(2*scale), 1)

    def test_numerical_failure_is_explicit(self):
        with self.assertRaises(ValueError):
            diffuse([1e308, 1e308], [], 0)
        with self.assertRaises(ValueError):
            diffuse([1, 0], [(0, 1, 1e308)], 1e308)
        with self.assertRaises(ValueError):
            harmony([1e300, -1e300], [1, 1], 0.5)

    def test_projection_does_not_mutate(self):
        x, caps = [3, -1], [2, 2]
        harmony(x, caps, 2)
        self.assertEqual(x, [3, -1])
        self.assertEqual(caps, [2, 2])

    def test_lattice_stress(self):
        for n in [10, 100, 1000]:
            edges = [(i, (i+1) % n, 1.0) for i in range(n)]
            state = [1000.0] + [0.0]*(n-1)
            for _ in range(100):
                lo, hi = min(state), max(state)
                state = diffuse(state, edges, 0.4)
                self.assertTrue(all(lo <= v <= hi for v in state))
                self.assertAlmostEqual(math.fsum(state), 1000, places=9)
            capped = harmony(state, [1000/n*2]*n, 1000)
            self.assertAlmostEqual(math.fsum(capped), 1000, places=8)


if __name__ == '__main__':
    unittest.main(verbosity=2)
