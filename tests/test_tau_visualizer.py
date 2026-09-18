import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'docker/scripts/tau'))
import copy
import json
import math
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from tau_engine import operate, validate


def lattice():
    return dict(version=1, phase=0, dt=0.25,
                nodes=[dict(id='a',energy=10,capacity=8,x=200,y=200),
                       dict(id='b',energy=0,capacity=8,x=400,y=300)],
                edges=[dict(source='a',target='b',weight=1)])


class VisualizerTests(unittest.TestCase):
    def test_complete_cycle(self):
        state = lattice()
        expected = [[10,0],[7.5,2.5],[7.5,2.5],[7.5,2.5]]
        for phase in range(4):
            result = operate(dict(action='step',state=state))
            state = result['state']
            self.assertEqual([n['energy'] for n in state['nodes']],expected[phase])
            self.assertEqual(state['phase'],(phase+1)%4)
            self.assertEqual(result['total'],10)

    def test_harmony_capacity_and_disconnected_graph(self):
        state=lattice();state['phase']=3;state['edges']=[]
        result=operate(dict(action='step',state=state))
        for value, expected in zip([n['energy'] for n in result['state']['nodes']],[8,2]):
            self.assertAlmostEqual(value,expected)
        self.assertIn('disconnected',result['message'])

    def test_spike_accounts_for_external_energy(self):
        state=lattice()
        result=operate(dict(action='spike',state=state,target='b',amount=5))
        self.assertEqual(result['total'],15)
        self.assertEqual(result['drift'],5)
        self.assertEqual(state,lattice())

    def test_failed_actions_are_atomic(self):
        state=lattice();before=copy.deepcopy(state)
        with self.assertRaises(ValueError):
            operate(dict(action='spike',state=state,target='a',amount=100))
        self.assertEqual(state,before)
        state['phase']=1;state['dt']=2;before=copy.deepcopy(state)
        with self.assertRaisesRegex(ValueError,'Unstable'):
            operate(dict(action='step',state=state))
        self.assertEqual(state,before)

    def test_import_roundtrip(self):
        state=lattice()
        self.assertEqual(validate(json.loads(json.dumps(state))),state)

    def test_invalid_imports(self):
        for field,value in [('nodes',[]),('edges',[dict(source='a',target='missing',weight=1)]),
                            ('phase',True),('dt',math.nan),('version',2)]:
            state=lattice();state[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):validate(state)
        state=lattice();state['edges']*=2
        with self.assertRaises(ValueError):validate(state)
        state=lattice();state['nodes'][0]['energy']=True
        with self.assertRaises(ValueError):validate(state)
