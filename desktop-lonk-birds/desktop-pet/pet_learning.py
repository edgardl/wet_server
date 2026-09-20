"""Small local learner: counted words/transitions, taught replies, sourced recall.

This is incremental associative learning, not a pretrained language model.
Only user text and explicitly supplied files update the language statistics.
"""
from __future__ import annotations

import math
import re
import unicodedata

WORD = re.compile(r"[^\W_]+(?:['’-][^\W_]+)*", re.UNICODE)
STOP = set('a an the is are was were be been being i me my you your we our they their it its this that these those of to in on at for and or but with from as do does did what when where why how can could would should tell about please have has had learned know remember say'.split())


def words(text):
    return WORD.findall(unicodedata.normalize('NFKC', text).casefold())


def key(text):
    return ' '.join(words(text))


class LanguageMemory:
    MAX_WORDS = 4000
    MAX_PASSAGES = 240
    MAX_FILES = 40

    def __init__(self, data=None, speaker='Lonk'):
        self.speaker = speaker
        self.data = data if data is not None else {}
        for name, value in {'version': 1, 'words': {}, 'next': {}, 'starts': {}, 'passages': [],
                            'taught': {}, 'files': [], 'history': [], 'name': '', 'turns': 0}.items():
            self.data.setdefault(name, value)
        if self.data['version'] != 1:
            raise ValueError('Unknown language memory version')
        for name in ('words', 'next', 'starts', 'taught'):
            if not isinstance(self.data[name], dict):
                raise ValueError('Invalid language memory: ' + name)
        for name in ('passages', 'files', 'history'):
            if not isinstance(self.data[name], list):
                raise ValueError('Invalid language memory: ' + name)

    @property
    def vocabulary(self):
        return len(self.data['words'])

    def observe(self, text, source, *, identity=False):
        if identity:
            match = re.search(r"\b(?:my name is|call me)\s+([^.!?\n]{1,50})", text, re.I)
            if match:
                self.data['name'] = match.group(1).strip()
        counts, transitions = self.data['words'], self.data['next']
        sentences = re.split(r'(?<=[.!?。！？])\s+|[\r\n]+', text[:45000])
        existing = {(p['text'], p['source']) for p in self.data['passages']}
        for raw in sentences:
            tokens = words(raw)
            if not tokens:
                continue
            accepted = []
            for token in tokens[:1000]:
                if len(token) > 48:
                    continue
                if token not in counts and len(counts) >= self.MAX_WORDS:
                    continue
                counts[token] = min(1_000_000, counts.get(token, 0) + 1)
                accepted.append(token)
            if accepted:
                first = accepted[0]
                starts = self.data['starts']
                starts[first] = min(1_000_000, starts.get(first, 0) + 1)
                for before, after in zip(accepted, accepted[1:] + ['<end>']):
                    next_words = transitions.setdefault(before, {})
                    if after in next_words or len(next_words) < 12:
                        next_words[after] = min(1_000_000, next_words.get(after, 0) + 1)
            passage = ' '.join(raw.split())[:480]
            # Questions teach vocabulary but are not stored as assertions to quote.
            if len(tokens) >= 3 and not raw.rstrip().endswith(('?', '？')) and (passage, source) not in existing:
                self.data['passages'].append({'text': passage, 'source': source})
                existing.add((passage, source))
        self.data['passages'] = self.data['passages'][-self.MAX_PASSAGES:]

    def record(self, role, text):
        self.data['history'].append({'role': role, 'text': text[:4000]})
        self.data['history'] = self.data['history'][-120:]

    def teach(self, prompt, reply):
        prompt, reply = prompt.strip(), reply.strip()
        if not prompt or not reply or len(prompt) > 300 or len(reply) > 1000:
            raise ValueError('Use a prompt up to 300 characters and a reply up to 1,000 characters.')
        if not key(prompt):
            raise ValueError('The phrase needs at least one word.')
        if key(prompt) not in self.data['taught'] and len(self.data['taught']) >= 200:
            raise ValueError('My 200 taught replies are full. You can still update an existing phrase.')
        self.data['taught'][key(prompt)] = reply
        self.observe(reply, 'You taught me')
        self.record('You', f'When I say "{prompt}", reply "{reply}".')
        self.record(self.speaker, 'coo! I will remember that reply.')

    def learn_file(self, document):
        digest = document['sha256']
        if any(f['sha256'] == digest for f in self.data['files']):
            return {'duplicate': True, 'new_words': 0}
        if len(self.data['files']) >= self.MAX_FILES:
            raise ValueError('My library is full (40 files). Chat and taught replies still work.')
        before = self.vocabulary
        name = str(document['name'])[:180]
        self.observe(document['text'], name)
        self.data['files'].append({'name': name, 'sha256': digest, 'characters': len(document['text']),
                                  'truncated': document['truncated']})
        gained = self.vocabulary - before
        note = f'I read {name} and picked up {gained} new words.'
        if document['truncated']:
            note += ' I read only the beginning (45,000 characters / up to 20 PDF pages).'
        self.record(self.speaker, note)
        return {'duplicate': False, 'new_words': gained, 'message': note}

    def choose(self, category, choices):
        rotations = self.data.setdefault('reply_rotation', {})
        index = rotations.get(category, 0)
        rotations[category] = index + 1
        return choices[index % len(choices)]

    def practice(self, rng):
        recent = self.data.setdefault('recent_practice', [])
        for _ in range(8):
            phrase = self._practice_once(rng)
            if phrase and phrase not in recent:
                recent.append(phrase)
                self.data['recent_practice'] = recent[-6:]
                return phrase
        return ''

    def _practice_once(self, rng):
        starts = self.data['starts']
        if not starts:
            return ''
        token = rng.choices(list(starts), weights=list(starts.values()), k=1)[0]
        result = []
        for _ in range(10):
            if token == '<end>':
                break
            result.append(token)
            choices = self.data['next'].get(token)
            if not choices:
                break
            token = rng.choices(list(choices), weights=list(choices.values()), k=1)[0]
        return ' '.join(result)

    def recall(self, text, exclude=None):
        query = set(words(text)) - STOP
        if not query:
            return None
        best, best_score = None, 0.0
        for passage in self.data['passages']:
            if exclude and key(passage['text']) == exclude:
                continue
            terms = set(words(passage['text'])) - STOP
            common = query & terms
            if not common:
                continue
            coverage = len(common) / len(query)
            if coverage < 0.35:
                continue
            score = coverage + len(common) / math.sqrt(max(1, len(terms)))
            if score > best_score:
                best, best_score = passage, score
        return best

    def respond(self, text, rng, *, learn=True):
        text = text.strip()
        if not text or len(text) > 4000 or not words(text):
            raise ValueError('Tell me something with words, up to 4,000 characters.')
        normalized = key(text)
        question = '?' in text or normalized.startswith(('what ', 'why ', 'how ', 'where ', 'when ', 'who ', 'tell me ', 'do you ', 'can you '))
        if normalized in self.data['taught']:
            reply = self.data['taught'][normalized]
        elif normalized in ('what is my name', 'whats my name', "what's my name", 'who am i'):
            reply = f'You told me your name is {self.data["name"]}. coo!' if self.data['name'] else "I don't know your name yet. Tell me: my name is ..."
        elif re.search(r'\b(?:my name is|call me)\s+', text, re.I):
            name = re.search(r'\b(?:my name is|call me)\s+([^.!?\n]{1,50})', text, re.I)
            reply = f'coo! Hello, {name.group(1).strip()}. I will remember your name.' if name else 'coo? What should I call you?'
        elif normalized in ('hi', 'hello', 'hey', 'hi lonk', 'hello lonk', 'hey lonk'):
            name = ', ' + self.data['name'] if self.data['name'] else ''
            reply = self.choose('hello', [f'Hey{name}! Good to see you.', f'Hello{name}. I saved you a spot beside my perch.', f'Hi{name}! What is happening in your corner of the world?', f'There you are{name}. My favorite visitor.'])
        elif normalized in ('how are you', 'how are you lonk'):
            reply = f'A little bird with {self.vocabulary} learned words and a lot of curiosity. How are you?'
        elif normalized in ('what have you learned', 'what do you know', 'what do you remember'):
            names = ', '.join(f['name'] for f in self.data['files'][-4:]) or 'no files yet'
            reply = f'I have picked up {self.vocabulary} words, {len(self.data["taught"])} taught replies, and {len(self.data["files"])} files. My latest reads: {names}.'
        else:
            recalled = self.recall(text, exclude=key(text))
            if recalled:
                source = recalled['source']
                lead = 'You told me' if source == 'You' else 'From ' + source
                reply = f'{lead}: “{recalled["text"]}”'
            elif question:
                reply = self.choose('unknown', ["I don't know that yet. We could explore it together.", "I don't know enough about that to give you a good answer. Is there something you can share with me?", "I don't know from what I have learned so far. A little more context would help."])
            else:
                novel = [w for w in words(text) if w not in self.data['words'] and w not in STOP]
                focus = ', '.join(dict.fromkeys(novel[:4]))
                reply = self.choose('listening', [f'I am listening. {focus.split(",")[0].capitalize()} caught my attention.' if focus else 'I am here, listening from my little perch.', 'That is something new for my little bird notebook.', 'What part of that matters most to you?', 'I like getting these little glimpses of your day.'])
        if learn:
            self.observe(text, 'You', identity=True)
            self.data['turns'] += 1
            self.record('You', text)
            self.record(self.speaker, reply)
        return reply