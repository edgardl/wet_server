"""Local Tau visualizer. Run: python -B visualizer.py; open printed URL."""
import argparse
import json
import math
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tau_model import diffuse, harmony

ROOT = Path(__file__).resolve().parent
LIMIT = 1_000_000


def number(value, label, maximum=1e9):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{label} must be a number')
    if not math.isfinite(value) or not 0 <= value <= maximum:
        raise ValueError(f'{label} must be finite and between 0 and {maximum:g}')
    return float(value)


def validate(raw):
    if not isinstance(raw, dict) or type(raw.get('version')) is not int or raw.get('version') != 1:
        raise ValueError('Expected lattice JSON with version 1')
    nodes, edges = raw.get('nodes'), raw.get('edges')
    if not isinstance(nodes, list) or not 1 <= len(nodes) <= 250:
        raise ValueError('Use between 1 and 250 nodes')
    if not isinstance(edges, list) or len(edges) > 4000:
        raise ValueError('Use at most 4000 connections')
    result, ids = [], set()
    for node in nodes:
        if not isinstance(node, dict):
            raise ValueError('Each node must be an object')
        ident = node.get('id')
        if not isinstance(ident, str) or not 1 <= len(ident) <= 40 or ident in ids:
            raise ValueError('Node IDs must be unique strings, 1-40 characters')
        ids.add(ident)
        result.append(dict(id=ident, energy=number(node.get('energy'), 'Energy'),
                           capacity=number(node.get('capacity'), 'Capacity'),
                           x=number(node.get('x'), 'X position', 1000),
                           y=number(node.get('y'), 'Y position', 700)))
    links, seen = [], set()
    for edge in edges:
        if not isinstance(edge, dict):
            raise ValueError('Each connection must be an object')
        a, b = edge.get('source'), edge.get('target')
        if not isinstance(a, str) or not isinstance(b, str) or a not in ids or b not in ids or a == b:
            raise ValueError('Connections need two different existing node IDs')
        key = tuple(sorted((a, b)))
        if key in seen:
            raise ValueError('Duplicate undirected connection')
        seen.add(key)
        links.append(dict(source=a, target=b, weight=number(edge.get('weight'), 'Weight')))
    dt = number(raw.get('dt', 0.2), 'Timestep', 10)
    phase = raw.get('phase', 0)
    if type(phase) is not int or phase not in range(4):
        raise ValueError('Phase must be an integer from 0 to 3')
    if math.fsum(n['energy'] for n in result) > math.fsum(n['capacity'] for n in result):
        raise ValueError('Total energy exceeds total capacity; increase capacities first')
    return dict(version=1, nodes=result, edges=links, dt=dt, phase=phase)


def operate(payload):
    if not isinstance(payload, dict):
        raise ValueError('Expected request object')
    state = validate(payload.get('state'))
    action = payload.get('action', 'validate')
    before = math.fsum(n['energy'] for n in state['nodes'])
    message = 'Lattice validated. Ready to explore.'
    if action == 'spike':
        amount = number(payload.get('amount'), 'Spike amount')
        target = next((n for n in state['nodes'] if n['id'] == payload.get('target')), None)
        if target is None:
            raise ValueError('Select a node for the energy spike')
        target['energy'] += amount
        state = validate(state)
        state['phase'] = 0
        message = f'Added {amount:g} energy from an external source; budget increased.'
    elif action == 'step':
        phase = state['phase']
        energy = [n['energy'] for n in state['nodes']]
        if phase == 0:
            message = 'F / Focus: highlight the highest-energy node. Energy unchanged.'
        elif phase == 1:
            indices = {n['id']: i for i, n in enumerate(state['nodes'])}
            edges = [(indices[e['source']], indices[e['target']], e['weight']) for e in state['edges']]
            energy = diffuse(energy, edges, state['dt'])
            message = 'D / Dissociate: synchronous conservative graph diffusion.'
        elif phase == 2:
            message = 'V / Volition: no external forcing configured. Energy unchanged.'
        else:
            energy = harmony(energy, [n['capacity'] for n in state['nodes']], before)
            message = 'H / Harmony: global capacity projection, including disconnected nodes.'
        for node, value in zip(state['nodes'], energy):
            node['energy'] = value
        state['phase'] = (phase + 1) % 4
    elif action != 'validate':
        raise ValueError('Unknown action')
    total = math.fsum(n['energy'] for n in state['nodes'])
    return dict(state=state, message=message, total=total, drift=total-before,
                peak=max(n['energy'] for n in state['nodes']))
