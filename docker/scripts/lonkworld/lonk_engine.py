"""XC record adapters and atomic persistence; simulation algorithms live in LonkWorld.xc."""
import copy
import json
import math
import os
import random
import re
import tempfile
from pathlib import Path
from functools import partial
import lonk_language as language
import lonk_society as society

SCHEMA = "lonkworld/2"
ACTIONS = ("attack", "explore", "think", "ouch", "idle")
EMOTIONS = ("power", "courage", "wisdom", "masochism", "joy", "anxiety")
TRAITS = ("aggression", "curiosity", "anxiety", "loyalty")

def _tuples(value):
    return tuple(_tuples(x) for x in value) if isinstance(value, list) else value

class _XCBacked:
    def __getattr__(self, name):
        if name.startswith('__'):
            raise AttributeError(name)
        world = self if self._xc_record == 'LonkWorld' else object.__getattribute__(self, 'world')
        record = world.controller.procedures.records[self._xc_record]
        if name in record.properties:
            return record.properties[name](self)
        if name in record.methods:
            return partial(record.methods[name], self)
        raise AttributeError(name)

class Lonk(_XCBacked):
    _xc_record = 'Lonk'

    def __init__(self, world, name=None):
        world.controller.procedures.records['Lonk'].methods['init'](self, world, name)

    def to_dict(self):
        return copy.deepcopy({k: v for k, v in self.__dict__.items() if k != 'world'})

class LonkWorld(_XCBacked):
    _xc_record = 'LonkWorld'

    def __init__(self, starting_population=5, max_population=20, controller=None, seed=2026):
        if controller is None or controller.procedures is None:
            raise ValueError('LonkWorld requires an XC source with its executable procedures.')
        self.controller = controller
        controller.procedures.records['LonkWorld'].methods['init'](
            self, starting_population, max_population, controller, seed)

    def to_dict(self):
        return {'schema': SCHEMA, 'tick': self.tick, 'max_population': self.max_population, 'source_hash': self.source_hash, 'next_uid': self.next_uid, 'toggles': copy.deepcopy(self.toggles), 'config': copy.deepcopy(self.config), 'colonies': copy.deepcopy(self.colonies), 'chronicle': copy.deepcopy(self.chronicle), 'next_colony_id': self.next_colony_id, 'rng_state': json.loads(json.dumps(self.rng.getstate())), 'lonks': [lonk.to_dict() for lonk in self.lonks]}

    def save(self, path):
        path = Path(path)
        payload = json.dumps(self.to_dict(), ensure_ascii=False, indent=2, allow_nan=False)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent, prefix=path.name + '.', suffix='.tmp', delete=False) as stream:
                temp_path = stream.name
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_path, path)
        finally:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)

    @classmethod
    def load(cls, path, controller=None):
        try:
            data = json.loads(Path(path).read_text(encoding='utf-8'))
            if not isinstance(data, dict) or data.get('schema') not in (SCHEMA, 'lonkworld/1'):
                raise ValueError(f'Unsupported world schema; expected {SCHEMA}')
            legacy = data['schema'] == 'lonkworld/1'
            if legacy and (controller is None or data.get('source_hash') not in controller.config.get('compatible_v1_hashes', [])):
                raise ValueError('This older world is not a recognized compatible LonkWorld version.')
            world = cls.__new__(cls)
            world.controller = controller
            world.source_hash = controller.source_hash if legacy else data.get('source_hash')
            world.tick = data['tick']
            world.max_population = data['max_population']
            world.next_uid = data['next_uid']
            if any((type(n) is not int for n in (world.tick, world.max_population, world.next_uid))):
                raise ValueError('World counters must be integers')
            if world.tick < 0 or world.max_population < 1 or world.next_uid < 1:
                raise ValueError('World counters are out of range')
            world.config = copy.deepcopy(controller.config) if legacy else data['config']
            if legacy:
                society.init_world(world)
            else:
                world.colonies = data['colonies']
                world.chronicle = data['chronicle']
                world.next_colony_id = data['next_colony_id']
            for key in ('territories', 'items', 'dialogue'):
                if not isinstance(world.config[key], dict) or not world.config[key]:
                    raise ValueError(f'Invalid world configuration: {key}')
            world.toggles = data['toggles']
            required_toggles = ('talk', 'violence', 'dreams', 'gossip', 'trauma', 'shinywars')
            if set(world.toggles) != set(required_toggles) or any((type(v) is not bool for v in world.toggles.values())):
                raise ValueError('Invalid world toggles')
            world.rng = random.Random()
            world.rng.setstate(_tuples(data['rng_state']))
            world.lonks = []
            seen = set()
            if not isinstance(data['lonks'], list) or len(data['lonks']) > world.max_population:
                raise ValueError('Invalid saved population')
            required = {'uid', 'name', 'state', 'emotion', 'personality', 'habits', 'age', 'lifespan', 'alive', 'generation', 'territory', 'faction', 'inventory', 'relationships', 'memory', 'long_memory', 'trauma', 'dopamine', 'crush', 'catchphrase', 'rival', 'xc_checkpoint'}
            if not legacy:
                required |= {'linguistics', 'social'}
            for record in data['lonks']:
                if not isinstance(record, dict) or set(record) != required:
                    raise ValueError('Invalid creature record fields')
                uid = record['uid']
                if not isinstance(uid, str) or not re.fullmatch('lonk-[1-9][0-9]*', uid) or uid in seen:
                    raise ValueError('Creature IDs must be unique stable IDs')
                if int(uid.split('-')[1]) >= world.next_uid:
                    raise ValueError('Creature ID counter would collide')
                seen.add(uid)
                if not isinstance(record['name'], str) or not record['name']:
                    raise ValueError('Creature name must be nonempty text')
                if type(record['alive']) is not bool:
                    raise ValueError('Invalid alive flag')
                for key in ('age', 'lifespan', 'generation'):
                    if type(record[key]) is not int or record[key] < (0 if key == 'age' else 1):
                        raise ValueError(f'Invalid creature {key}')
                for key, expected in (('emotion', EMOTIONS), ('personality', TRAITS), ('habits', ACTIONS)):
                    if not isinstance(record[key], dict) or set(record[key]) != set(expected):
                        raise ValueError(f'Invalid creature {key}')
                if not isinstance(record['state'], list) or len(record['state']) != 5:
                    raise ValueError('Creature state must have five numbers')
                for key in ('inventory', 'long_memory'):
                    if not isinstance(record[key], list) or len(record[key]) > (32 if key == 'inventory' else 128):
                        raise ValueError(f'Invalid bounded {key}')
                if record['territory'] not in world.config['territories'] or record['faction'] not in world.config['factions']:
                    raise ValueError('Unknown territory or faction')
                if not isinstance(record['relationships'], dict):
                    raise ValueError('Relationships must be a dictionary')
                if record['xc_checkpoint'] is not None and (not isinstance(record['xc_checkpoint'], dict)):
                    raise ValueError('XC checkpoint must be an object or null')
                memory = record['memory']
                for key in ('player_words', 'lonk_words', 'word_counts'):
                    if not isinstance(memory[key], dict) or len(memory[key]) > 256:
                        raise ValueError('Invalid vocabulary')
                    if any((not isinstance(k, str) or type(v) is not int or (not 0 <= v <= 1000000) for k, v in memory[key].items())):
                        raise ValueError('Invalid word counts')
                for key in ('rumors', 'events', 'player_interactions'):
                    if not isinstance(memory[key], list) or len(memory[key]) > (32 if key == 'rumors' else 64):
                        raise ValueError('Invalid bounded memory')
                    if any((not isinstance(entry, dict) or not isinstance(entry.get('text'), str) for entry in memory[key])):
                        raise ValueError('Memory entries must contain text')
                lonk = Lonk.__new__(Lonk)
                lonk.__dict__.update(copy.deepcopy(record))
                lonk.world = world
                if legacy:
                    lonk.linguistics = language.initial_language(controller)
                    society.init_lonk(lonk)
                    if lonk.xc_checkpoint is not None:
                        lonk.xc_checkpoint['source_sha256'] = controller.source_hash
                else:
                    language.validate(lonk)
                numbers = [(n, 0, 1) for n in lonk.state]
                numbers += [(n, 0, 100) for n in list(lonk.emotion.values()) + list(lonk.personality.values()) + [lonk.trauma, lonk.dopamine]]
                numbers += [(n, 0, 1000) for n in lonk.habits.values()]
                numbers += [(n, -100, 100) for n in lonk.relationships.values()]
                if any((type(n) not in (int, float) or not math.isfinite(n) or (not low <= n <= high) for n, low, high in numbers)):
                    raise ValueError('Creature stats must be finite and within bounds')
                world.lonks.append(lonk)
            if legacy:
                rng_before = world.rng.getstate()
                for lonk in world.lonks:
                    for entry in lonk.memory['player_interactions']:
                        language.learn(lonk, entry['text'], speaker_id='player')
                    for entry in lonk.memory['rumors']:
                        language.learn(lonk, entry['text'], speaker_id=str(entry.get('source', 'world')))
                    if not lonk.linguistics['tokens'] and lonk.memory['word_counts']:
                        language.learn(lonk, ' '.join(lonk.memory['word_counts']), speaker_id='inherited')
                    lonk.social['conversations'] = len(lonk.memory['player_interactions'])
                world.rng.setstate(rng_before)
                world.migration_note = 'Your existing Lonks and memories are safe. Learned speech, colonies and multiple partnerships are now available.'
            if controller is None:
                raise ValueError('An XC application controller is required to load a world.')
            controller.validate_world(world)
            society.validate_world(world)
            return world
        except (OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError) as exc:
            raise ValueError(f'Cannot load LonkWorld save: {exc}') from exc
