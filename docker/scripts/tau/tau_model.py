"""Conservative graph diffusion and capped-simplex projection; no dependencies."""
import math


def _finite(values, label, nonnegative=False):
    result = [float(v) for v in values]
    if not result or any(not math.isfinite(v) or (nonnegative and v < 0)
                         for v in result):
        raise ValueError(f'{label} must be nonempty and finite' +
                         (' and nonnegative' if nonnegative else ''))
    return result


def _sum(values):
    try:
        result = math.fsum(values)
    except OverflowError as exc:
        raise ValueError('Aggregate exceeds floating-point range') from exc
    if not math.isfinite(result):
        raise ValueError('Aggregate exceeds floating-point range')
    return result


def diffuse(energy, edges, dt):
    """Unique undirected (i,j,weight) edges; synchronous convex update.

    Requires dt >= 0 and dt * weighted_degree <= 1 at every node.
    Conserves total energy in exact arithmetic; floating-point rounding applies.
    Inputs are never mutated. Self edges and duplicate edges are rejected.
    """
    old = _finite(energy, 'energy', True)
    _sum(old)
    dt = float(dt)
    if not math.isfinite(dt) or dt < 0:
        raise ValueError('dt must be finite and nonnegative')
    neighbors = [[] for _ in old]
    seen = set()
    for i, j, weight in edges:
        if (type(i) is not int or type(j) is not int or
                not 0 <= i < len(old) or not 0 <= j < len(old) or i == j):
            raise ValueError('Invalid edge endpoints')
        key = (min(i, j), max(i, j))
        if key in seen:
            raise ValueError('Each undirected edge must occur once')
        seen.add(key)
        weight = float(weight)
        if not math.isfinite(weight) or weight < 0:
            raise ValueError('Weights must be finite and nonnegative')
        coefficient = dt * weight
        if not math.isfinite(coefficient):
            raise ValueError('Timestep coefficient overflow')
        neighbors[i].append((j, coefficient))
        neighbors[j].append((i, coefficient))
    degrees = [_sum(a for _, a in row) for row in neighbors]
    if any(d > 1 for d in degrees):
        raise ValueError('Unstable timestep: dt * weighted degree exceeds 1')
    return [_sum([(1-degrees[i])*old[i]] +
                 [a*old[j] for j, a in row])
            for i, row in enumerate(neighbors)]


def harmony(proposal, capacities, budget):
    """Euclidean projection onto 0 <= y <= capacities, sum(y) = budget.

    Returns a new list. Uses scaled bisection and checks relative budget error
    <= 1e-12. Numerically unresolved inputs raise ValueError rather than silently
    claiming conservation. This is not a topological or gauge invariant.
    """
    x = _finite(proposal, 'proposal')
    caps = _finite(capacities, 'capacities', True)
    budget = float(budget)
    if len(x) != len(caps):
        raise ValueError('Proposal and capacities must have equal lengths')
    total_capacity = _sum(caps)
    if not math.isfinite(budget) or not 0 <= budget <= total_capacity:
        raise ValueError('Infeasible or nonfinite budget')
    if budget == 0:
        return [0.0]*len(x)
    if budget == total_capacity:
        return caps.copy()
    if all(0 <= v <= c for v, c in zip(x, caps)) and _sum(x) == budget:
        return x.copy()
    scale = max(max(abs(v) for v in x), max(caps), budget)
    xs = [v/scale for v in x]
    cs = [c/scale for c in caps]
    target = budget/scale
    if target == 0:
        raise ValueError('Budget is below working numerical resolution')
    low = min(v-c for v, c in zip(xs, cs))
    high = max(xs)
    for _ in range(256):
        level = low + (high-low)/2
        ys = [min(c, max(0.0, v-level)) for v, c in zip(xs, cs)]
        total = _sum(ys)
        if abs(total-target) <= 1e-14*target:
            break
        if total > target:
            low = level
        else:
            high = level
    result = [min(c, max(0.0, v*scale)) for v, c in zip(ys, caps)]
    if abs(_sum(result)-budget) > 1e-12*budget:
        raise ValueError('Projection cannot resolve the requested energy budget')
    return result
