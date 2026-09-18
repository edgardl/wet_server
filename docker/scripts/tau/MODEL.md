# Conservative graph reference experiment

Standalone Python standard-library reference for the proposed redistribution
and Harmony contracts. Does not modify or integrate with the XC runtime.

Run from this directory:

```powershell
python -B test_model.py
python -B demo.py
```

The demo writes `report.json`: 10, 100, and 1000 nodes, an initial energy spike
of 1000, 100 synchronous diffusion steps, then capacity projection.

## Contracts

`diffuse(energy, edges, dt)` accepts nonnegative finite energies and unique
undirected `(i, j, weight)` edges. Weights must be finite and nonnegative.
Requires `dt >= 0` and `dt * weighted_degree <= 1` at every node.
It computes a fresh snapshot using convex combinations. In exact arithmetic,
this preserves total energy, nonnegativity, and the previous min/max bounds.
An equality timestep can oscillate: boundedness does not imply convergence.

`harmony(proposal, capacities, budget)` minimizes half the squared Euclidean
distance to the proposal subject to nonnegative node capacities and the given
total energy. The budget must be feasible. Scaled bisection finds the common
threshold in `min(capacity, max(0, proposal - threshold))`.
Floating-point output must satisfy relative budget error at most 1e-12;
unresolved precision raises ValueError. Inputs are not mutated.
NaN, infinity, overflowing aggregates, and invalid contracts are rejected.

Tests cover analytical answers, timestep boundaries, isolated nodes, malformed
edges, infeasible budgets, negative/nonfinite energy, extreme finite scales,
randomized projection optimality, and repeated finite-spike diffusion.

## Limits

These are graph-model numerical guarantees, not evidence of physical
singularity removal, topological invariance, gauge invariance, or a new fluid
law. Global capacity projection can move energy between disconnected nodes;
it models an explicitly global allocation operation, not local transport.
Focus, Volition, gauge dynamics, and physical validation are not implemented.
No guarantee is made for arbitrary dynamic ranges beyond the numerical checks.

## Tau Connection Visualizer

Double-click **Launch Tau.cmd** on Windows, or run:

```powershell
python -X utf8 -B visualizer.py --open
```

Visit http://127.0.0.1:8765. Keep the terminal open; Ctrl+C stops the server.
Use `--port 8766` if that port is occupied. Python 3.10+ is required; there
are no runtime packages, CDN requests, or external service dependencies.

- Select, drag, add, or remove nodes. Arrow keys move a focused node.
- Apply node energy/capacity changes, set/remove weighted connections.
- Play, pause, or step the phase sequence. The highlighted phase is next.
- Inject a finite spike; its external energy is explicitly added to the budget.
- Save/load JSON; invalid edits/imports leave the current lattice intact.
- Reset demo restores the six-node preset. Save before reloading the page.

Phase definitions in this prototype:
F observes the energy distribution (no amplification); D runs conservative
snapshot diffusion; V is an explicit identity step (no forcing configured);
H projects globally onto capacities. The positions are drawing coordinates,
not physical geometry. Animated edges indicate the energy gradient, not a
measured physical particle trajectory. Dashed red node rings mark overcapacity.

JSON uses `version: 1`, `phase: 0..3`, `dt`, `nodes` and `edges`. Each node has
`id`, `energy`, `capacity`, `x` (0..1000), `y` (0..700). Each undirected edge
has `source`, `target`, and nonnegative `weight`. Up to 250 nodes, 4000 edges,
and 1 MB per import; total energy must fit total capacity. The diffusion phase
rejects unstable timesteps. This version supports JSON, not CSV/XC/XIR export.

Verification:

```powershell
python -X utf8 -B -m unittest discover -s . -p "test_*.py" -v
node --check app.js
node browser_smoke.mjs
```

The optional browser test uses Node 22+ and installed Microsoft Edge on Windows.
Set `TAU_PYTHON` and `TAU_BROWSER` to override executable locations. It owns and
cleans up its temporary server/browser, writes `visualizer-browser-report.json`,
and captures desktop/mobile PNGs. Runtime use requires only Python and a browser.
