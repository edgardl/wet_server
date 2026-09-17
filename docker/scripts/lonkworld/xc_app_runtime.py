"""XC application host extension 1.0; native XC semantics remain in xc_runtime.

Adds a declarative `application NAME { JSON manifest }` followed by one
native `xembra` model. Scalar assignments lower to native vector assignments.
The manifest binds numerical model fields to host creature attributes. No
Python eval/exec is used to interpret application source.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re

import xc_runtime as xc
from xc_procedures import XCProcedures


class XCApplication:
    def __init__(self, path):
        self.path = Path(path)
        text = self.path.read_text(encoding="utf-8-sig")
        self.source_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        match = re.match(r"\s*application\s+([A-Za-z_]\w*)\s*", text)
        if not match:
            raise ValueError("XC application must begin with 'application Name { ... }'.")
        self.name = match.group(1)
        try:
            self.config, consumed = json.JSONDecoder().raw_decode(text[match.end():])
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid XC application declaration: {exc}") from exc
        if not isinstance(self.config, dict) or self.config.get("host_version") != 1:
            raise ValueError("This runner requires XC application host_version 1.")
        source = text[match.end() + consumed:]
        procedural_start = re.search(r'^procedures\s+\w+\s+version\s+1\s*\{', source, re.MULTILINE)
        native_source = source[:procedural_start.start()] if procedural_start else source
        self.ir = xc.Parser(xc.tokenize(native_source)).parse()
        self.ir["source"] = {"name": self.path.name, "sha256": self.source_hash}
        self._lower_scalar_updates()
        prototype = xc.Runtime(self.ir)
        self.fields = prototype.field_names
        self.bindings = self.config.get("bindings", {})
        self.inputs = self.config.get("inputs", {})
        if not isinstance(self.bindings, dict) or not isinstance(self.inputs, dict):
            raise ValueError("bindings and inputs must be objects.")
        for field, binding in self.bindings.items():
            if field not in self.fields or not re.fullmatch(
                r"(?:state\.[0-4]|emotion\.[a-z_]+|personality\.[a-z_]+|trauma|dopamine)", binding
            ):
                raise ValueError(f"Invalid host binding: {field} -> {binding}")
        for field, distribution in self.inputs.items():
            if field not in self.fields or distribution not in {"uniform", "centered_uniform", "gumbel"}:
                raise ValueError(f"Invalid random input: {field}")
        if set(self.bindings) & set(self.inputs):
            raise ValueError("A field cannot be both a binding and a random input.")
        if "Tick" not in self.ir["program"]["events"]:
            raise ValueError("The creature model must declare event Tick.")
        self._validate_config()
        self.procedures = None
        if procedural_start:
            import copy
            import random
            from lonk_engine import Lonk
            self.procedures = XCProcedures(source[procedural_start.start():], {
                'math': math, 're': re, 'copy': copy, 'random': random, 'Lonk': Lonk,
            })

    def _validate_config(self):
        world = self.config.get("world", {})
        for name, default, lo, hi in (("starting_population", 5, 0, 100), ("max_population", 20, 1, 100)):
            value = world.get(name, default)
            if type(value) is not int or not lo <= value <= hi:
                raise ValueError(f"world.{name} must be an integer from {lo} to {hi}.")
        if world.get("starting_population", 5) > world.get("max_population", 20):
            raise ValueError("Starting population exceeds maximum population.")
        # One authoritative population declaration for both GUI and host.
        self.config["starting_population"] = world["starting_population"]
        self.config["max_population"] = world["max_population"]
        for key in ("social_chance", "rumor_mutation_chance", "speech_chance", "dream_chance",
                    "relationship_decay", "rebirth_chance", "arrival_chance", "item_chance",
                    "crush_chance", "catchphrase_chance", "recall_chance"):
            value = world.get(key)
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"world.{key} must be a finite probability between 0 and 1.")
        for key in ("name_start", "name_end", "factions"):
            values = self.config.get(key)
            if not isinstance(values, list) or not values or any(not isinstance(x, str) or not x for x in values):
                raise ValueError(f"{key} must contain nonempty strings.")
        for key in ("territories", "items", "dialogue", "keywords"):
            if not isinstance(self.config.get(key), dict) or not self.config[key]:
                raise ValueError(f"{key} must be a nonempty object.")
        for key in ("initial_stats", "lifespan"):
            pair = world.get(key)
            if not isinstance(pair, list) or len(pair) != 2 or any(type(x) is not int for x in pair) or pair[0] > pair[1]:
                raise ValueError(f"world.{key} must be two ordered integers.")
        if not 0 <= world['initial_stats'][0] <= world['initial_stats'][1] <= 100 or world['lifespan'][0] < 1:
            raise ValueError("Initial stats or lifespan are out of bounds.")
        initial = world.get("initial_state")
        if not isinstance(initial, list) or len(initial) != 5 or any(type(x) not in (int, float) or not 0 <= x <= 1 for x in initial):
            raise ValueError("initial_state must contain five numbers between 0 and 1.")

    def _lower_scalar_updates(self):
        p = self.ir["program"]
        if len(p["states"]) != 1:
            raise ValueError("One creature state block is required.")
        state_name, state = next(iter(p["states"].items()))
        names = [f["name"] for f in state["fields"]]
        groups = [p["cycle"]] + [e["statements"] for e in p["events"].values()]
        for group in groups:
            for statement in group:
                target = statement.get("target")
                if target in names:
                    expr = statement["expr"]
                    statement["target"] = state_name
                    statement["expr"] = {"kind": "list", "items": [
                        expr if field == target else {"kind": "ident", "name": field}
                        for field in names
                    ]}

    def _runtime(self, lonk):
        return xc.Runtime(self.ir, checkpoint_data=lonk.xc_checkpoint)

    @staticmethod
    def _read(lonk, path):
        parts = path.split(".")
        value = getattr(lonk, parts[0])
        if len(parts) > 1:
            value = value[int(parts[1])] if parts[0] == "state" else value[parts[1]]
        value = float(value)
        if not math.isfinite(value):
            raise ValueError(f"Non-finite creature value in {path}")
        return value

    @staticmethod
    def _write(lonk, path, value):
        if not math.isfinite(value):
            raise ValueError(f"XC returned a non-finite value in {path}")
        parts = path.split(".")
        if len(parts) == 1:
            setattr(lonk, parts[0], value)
        else:
            target = getattr(lonk, parts[0])
            target[int(parts[1]) if parts[0] == "state" else parts[1]] = value

    def _dispatch(self, lonk, name):
        if name not in self.ir["program"]["events"]:
            raise ValueError(f"LonkWorld.xc is missing event {name}.")
        rt = self._runtime(lonk)
        for field, path in self.bindings.items():
            rt.state[self.fields.index(field)] = self._read(lonk, path)
        if 'trauma_enabled' in self.fields:
            rt.state[self.fields.index('trauma_enabled')] = float(lonk.world.toggles['trauma'])
        # Declarative item/territory effects live in the application source.
        effects = {}
        if name == 'territory':
            place = self.config['territories'][lonk.territory]
            effects = dict(place.get('bonus', {}))
            if place.get('faction_bonus') == lonk.faction:
                effects['loyalty'] = effects.get('loyalty', 0) + 5
                effects['power'] = effects.get('power', 0) + 3
        elif name == 'find_item' and lonk.inventory:
            effects = self.config['items'][lonk.inventory[-1]].get('effect', {})
        for field, amount in effects.items():
            if field not in self.fields:
                raise ValueError(f'Unknown effect field {field}')
            index = self.fields.index(field)
            rt.state[index] = max(0, min(100, rt.state[index] + float(amount)))
        if name == "Tick":
            for field, distribution in self.inputs.items():
                value = lonk.world.rng.random()
                if distribution == "centered_uniform":
                    value -= 0.5
                elif distribution == "gumbel":
                    value = -math.log(-math.log(max(1e-15, min(1 - 1e-15, value))))
                rt.state[self.fields.index(field)] = value
        rt.dispatch(name)
        values = rt.state_dict()
        # Validate all outputs before updating host state.
        if any(not math.isfinite(v) for v in values.values()):
            raise ValueError("XC produced non-finite creature state.")
        for field, path in self.bindings.items():
            self._write(lonk, path, values[field])
        lonk.xc_checkpoint = rt.export_checkpoint()
        return rt.action.lower() if rt.action else "idle"

    def step(self, lonk):
        return self._dispatch(lonk, "Tick")

    def event(self, lonk, event_name):
        self._dispatch(lonk, event_name)
        return True

    def validate_world(self, world):
        if world.source_hash != self.source_hash:
            raise ValueError('This save belongs to a different version of LonkWorld.xc. Restore its source or choose New World.')
        for lonk in world.lonks:
            if lonk.xc_checkpoint is not None:
                self._runtime(lonk)
