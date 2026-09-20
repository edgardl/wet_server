import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from desktop_pet import Brain, Playground, SOURCE


class PetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.brain = Brain(self.root / 'pet', seed=12)

    def test_autonomous_xc_creates_real_files_and_audits(self):
        for _ in range(200):
            self.brain.tick()
        files = self.brain.playground.files()
        self.assertGreaterEqual(len(files), 1)
        self.assertLessEqual(len(files), 3)
        self.assertTrue(all(p.stat().st_size > 100 for p in files))
        receipts = [json.loads(s) for s in (self.brain.data / 'actions.jsonl').read_text().splitlines()]
        creations = [r for r in receipts if r['action'] in ('draw', 'note')]
        self.assertEqual(len(creations), len(files))
        self.assertTrue(all(r['success'] for r in creations))
        self.assertTrue(all(r['source_sha256'] == self.brain.source_hash for r in receipts))

    def test_creations_disabled_but_explicit_request_works(self):
        self.brain.settings['create'] = False
        for _ in range(200):
            self.brain.tick()
        self.assertEqual(self.brain.playground.files(), [])
        self.brain.tick('note')
        self.assertEqual(len(self.brain.playground.files()), 1)

    def test_memory_settings_and_rng_survive_restart(self):
        self.brain.tick('pet')
        self.brain.settings['windows'] = True
        self.brain.save()
        resumed = Brain(self.brain.data)
        self.assertEqual(resumed.state, self.brain.state)
        self.assertEqual(resumed.settings, self.brain.settings)
        self.assertEqual(resumed.rng.random(), self.brain.rng.random())
        resumed.tick('note')
        self.assertIn('Head pats received: 1', resumed.playground.last.read_text())

    def test_xc_edit_changes_actual_pet_behavior(self):
        changed = self.root / 'Different.xc'
        changed.write_text(SOURCE.read_text().replace("s['affection'] + 1", "s['affection'] + 7"))
        alternate = Brain(self.root / 'alternate', source=changed)
        self.brain.tick('pet')
        alternate.tick('pet')
        self.assertEqual(self.brain.state['affection'], 1)
        self.assertEqual(alternate.state['affection'], 7)

    def test_outside_file_cannot_be_opened(self):
        outside = self.root / 'private.txt'
        outside.write_text('not a pet creation')
        with patch('os.startfile') as launch:
            with self.assertRaises(ValueError):
                self.brain.playground.open_creation(outside)
            launch.assert_not_called()

    def test_opening_real_creation_uses_registered_association(self):
        self.brain.tick('draw')
        with patch('os.startfile') as launch:
            self.brain.open_last()
            launch.assert_called_once_with(str(self.brain.playground.last))

    def test_file_capacity_does_not_claim_success(self):
        self.brain.playground.LIMIT = 1
        self.brain.tick('draw')
        self.brain.tick('note')
        self.assertEqual(self.brain.state['creations'], 1)
        self.assertEqual(len(self.brain.playground.files()), 1)
        self.assertIn('collection is full', self.brain.message)
        last = json.loads((self.brain.data / 'actions.jsonl').read_text().splitlines()[-1])
        self.assertFalse(last['success'])

    def test_window_titles_are_opt_in_and_not_persisted(self):
        self.brain.tick(window='private title one')
        self.assertEqual(self.brain.last_window, '')
        self.brain.settings['windows'] = True
        self.brain.tick(window='private title one')
        result = self.brain.tick(window='private title two')
        self.assertEqual(result['action'], 'watch')
        self.brain.save()
        self.assertNotIn('private title', (self.brain.data / 'state.json').read_text())

    def test_corrupt_save_is_preserved(self):
        self.brain.save()
        save = self.brain.data / 'state.json'
        save.write_text('{broken')
        with self.assertRaises(ValueError):
            Brain(self.brain.data)
        self.assertEqual(save.read_text(), '{broken')

    def test_low_energy_rests_then_recovers(self):
        self.brain.state['energy'] = 5
        self.assertEqual(self.brain.tick()['action'], 'rest')
        for _ in range(40):
            self.brain.tick()
        self.assertGreater(self.brain.state['energy'], 60)


if __name__ == '__main__':
    unittest.main()
