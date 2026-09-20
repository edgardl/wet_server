import json
from pathlib import Path
import random
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from desktop_pet import Brain
from pet_conversation import LocalChat, ChatCancelled, make_context


class ConversationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.lonk = Brain(self.root, seed=12)
        self.pip = Brain(self.root / 'Pip', seed=34, name='Pip')

    def test_friend_has_independent_state_language_and_save(self):
        self.lonk.tick('pet')
        self.lonk.talk('My name is Robin.')
        self.pip.talk('Sunflowers follow the sun.')
        self.assertEqual(self.lonk.state['affection'], 1)
        self.assertEqual(self.pip.state['affection'], 0)
        self.assertEqual(self.pip.language.data['name'], '')
        self.assertNotIn('sunflowers', self.lonk.language.data['words'])
        self.assertEqual(Brain(self.pip.data, name='Pip').name, 'Pip')
        self.assertEqual(Brain(self.lonk.data).language.data['name'], 'Robin')

    def test_model_reply_does_not_retrain_language_or_duplicate_user(self):
        snapshot = self.lonk.begin_chat('I like moonberry jam.')
        before = dict(self.lonk.language.data['words'])
        self.lonk.finish_chat('Would you put it on toast?', 'local')
        self.assertEqual(before, self.lonk.language.data['words'])
        self.assertEqual(self.lonk.language.data['turns'], 1)
        self.assertEqual(len(self.lonk.language.data['history']), 2)
        self.assertEqual(snapshot['message'], 'I like moonberry jam.')

    def test_context_contains_history_and_relevant_file_but_not_friends_files(self):
        self.lonk.learn_document({'name': 'garden.txt', 'text': 'Nebula pears glow violet at midnight.', 'sha256': 'a', 'truncated': False})
        self.pip.learn_document({'name': 'secret.txt', 'text': 'Pip has private nectarine notes.', 'sha256': 'b', 'truncated': False})
        self.lonk.talk('My name is Robin.')
        snapshot = self.lonk.begin_chat('What color are nebula pears?')
        messages = make_context(snapshot)
        payload = json.dumps(messages)
        self.assertIn('violet', payload)
        self.assertIn('garden.txt', payload)
        self.assertIn('Robin', payload)
        self.assertNotIn('nectarine', payload)
        self.assertEqual(messages[-1]['content'], snapshot['message'])

    def test_taught_reply_takes_precedence(self):
        self.pip.teach('goodnight', 'sleep softly, little moon')
        request = self.pip.begin_chat('Goodnight!')
        self.assertEqual(request['taught_reply'], 'sleep softly, little moon')

    def test_offline_greetings_vary(self):
        replies = [self.lonk.talk('hello') for _ in range(5)]
        self.assertGreaterEqual(len(set(replies)), 3)
        self.assertNotEqual(replies[0], replies[1])

    def test_social_meeting_updates_each_bird_once_without_training_generated_text(self):
        before = self.lonk.language.vocabulary
        a = self.lonk.meet('Pip')
        b = self.pip.meet('Lonk')
        self.assertEqual(self.lonk.state['friend_visits'], 1)
        self.assertEqual(self.pip.state['friend_visits'], 1)
        self.assertIn('Pip', self.lonk.state['memories'][-1])
        self.assertIn('Lonk', self.pip.state['memories'][-1])
        self.assertEqual(self.lonk.language.vocabulary, before)
        self.assertTrue(a and b)

    def test_new_conversation_preserves_original_pet_memory(self):
        self.lonk.tick('pet')
        self.lonk.talk('My name is Robin.')
        reopened = Brain(self.root)
        self.assertEqual(reopened.state['affection'], 1)
        self.assertEqual(reopened.language.data['name'], 'Robin')
        self.assertGreater(len(reopened.language.data['history']), 0)


class Handler(BaseHTTPRequestHandler):
    cloud = False
    incomplete = False
    posted = []

    def log_message(self, *args):
        pass

    def do_GET(self):
        body = json.dumps({'models': [{'name': 'qwen3:8b', 'remote_host': 'cloud.example' if self.cloud else None}]}).encode()
        self.send_response(200); self.end_headers(); self.wfile.write(body)

    def do_POST(self):
        self.posted.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
        self.send_response(200); self.end_headers()
        events = [{'message': {'content': 'Hello '}, 'done': False}, {'message': {'content': 'Pip.'}, 'done': False}]
        if not self.incomplete:
            events.append({'message': {'content': ''}, 'done': True})
        for event in events:
            try:
                self.wfile.write(json.dumps(event).encode() + b'\n'); self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                break


class TransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join()

    def setUp(self):
        Handler.cloud = Handler.incomplete = False
        Handler.posted = []
        self.client = LocalChat(port=self.server.server_port)
        self.snapshot = {'name': 'Lonk', 'friend': 'Pip', 'personality': 'curious', 'message': 'hi',
                         'history': [], 'memories': [], 'facts': [], 'user_name': '', 'energy': 80}

    def test_streamed_local_reply_and_no_tool_authority(self):
        pieces = []
        answer = self.client.generate(self.snapshot, threading.Event(), pieces.append)
        self.assertEqual(answer, 'Hello Pip.')
        self.assertEqual(''.join(pieces), answer)
        request = Handler.posted[0]
        self.assertFalse(request['think'])
        self.assertTrue(request['stream'])
        self.assertNotIn('tools', request)

    def test_remote_model_is_rejected_before_chat_is_sent(self):
        Handler.cloud = True
        with self.assertRaisesRegex(ValueError, 'local'):
            self.client.generate(self.snapshot, threading.Event(), lambda x: None)
        self.assertEqual(Handler.posted, [])

    def test_cancel_does_not_return_a_final_reply(self):
        cancel = threading.Event()
        with self.assertRaises(ChatCancelled):
            self.client.generate(self.snapshot, cancel, lambda x: cancel.set())

    def test_incomplete_stream_is_not_claimed_as_a_complete_reply(self):
        Handler.incomplete = True
        with self.assertRaisesRegex(ValueError, 'complete'):
            self.client.generate(self.snapshot, threading.Event(), lambda x: None)


if __name__ == '__main__':
    unittest.main()