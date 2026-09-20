"""A visible XC-driven Windows pet with bounded, real desktop capabilities."""
from __future__ import annotations

import argparse
import copy
import ctypes
from ctypes import wintypes
import hashlib
import json
import math
import os
from pathlib import Path
import random
import sys
import tempfile
import time
import traceback
import uuid

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'desktop-lonkworld'))
from xc_procedures import XCProcedures
from pet_learning import LanguageMemory, key, words

SOURCE = HERE / 'DesktopLonk.xc'
DATA = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'DesktopLonkXC'
KEY = '#ff00ff'


class Playground:
    """Fixed actions only. XC does not receive this object or OS primitives."""
    LIMIT = 150

    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.last = None

    def files(self):
        return sorted(p for p in self.root.iterdir()
                      if p.is_file() and not p.is_symlink() and p.suffix in ('.svg', '.txt'))

    def create(self, kind, content):
        if kind not in ('draw', 'note'):
            raise ValueError('Unknown playground capability')
        if len(self.files()) >= self.LIMIT:
            raise ValueError('My collection is full (150 files). Move some out to make room.')
        if len(content.encode('utf-8')) > 64_000:
            raise ValueError('Creation is too large')
        extension = '.svg' if kind == 'draw' else '.txt'
        name = f"lonk-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}{extension}"
        target = self.root / name
        with target.open('x', encoding='utf-8') as stream:
            stream.write(content)
        self.last = target
        return target

    def open_creation(self, path=None):
        path = Path(path or self.last).resolve() if (path or self.last) else None
        if path is None:
            raise ValueError('No creation to open yet')
        if path.parent != self.root or path.suffix not in ('.txt', '.svg') or not path.is_file():
            raise ValueError('Only creations inside the playground can be opened')
        os.startfile(str(path))

    def open_folder(self):
        os.startfile(str(self.root))


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    with temporary.open('w', encoding='utf-8') as stream:
        json.dump(data, stream, indent=2, allow_nan=False)
    os.replace(temporary, path)


class Brain:
    def __init__(self, data, source=SOURCE, seed=None, name='Lonk'):
        self.data = Path(data)
        self.data.mkdir(parents=True, exist_ok=True)
        text = Path(source).read_text(encoding='utf-8')
        self.source_hash = hashlib.sha256(text.encode()).hexdigest()
        self.code = XCProcedures(text, max_steps=20_000).namespaces['pet']
        self.state = self.code.born()
        self.rng = random.Random(seed)
        self.playground = Playground(self.data / 'Playground')
        self.settings = {'create': True, 'windows': False, 'show_creations': False, 'local_chat': True}
        saved = self.data / 'state.json'
        if saved.exists():
            self.load(saved)
        self.last_window = ''
        self.last_action = 'wander'
        self.message = 'coo! double-click me to talk'
        identity = self.state.setdefault('identity', {'name': name})
        self.name = identity['name']
        self.personality = ('gentle, curious, thoughtful, with dry little bird jokes' if self.name == 'Lonk'
                            else 'sunny, playful, a little adventurous, fond of shiny things')
        self.state.setdefault('friend_visits', 0)
        self.language = LanguageMemory(self.state.setdefault('language', {}), speaker=self.name)

    def load(self, saved):
        document = json.loads(saved.read_text(encoding='utf-8'))
        state = document['state']
        if state.get('version') != 1:
            raise ValueError('Unsupported pet save version; existing save was not changed')
        for key in ('ticks', 'energy', 'curiosity', 'affection', 'creations', 'last_create'):
            value = state[key]
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError(f'Invalid saved {key}; existing save was not changed')
        if not isinstance(state['memories'], list) or not all(isinstance(x, str) for x in state['memories']):
            raise ValueError('Invalid saved memories')
        self.state = state
        for key in self.settings:
            self.settings[key] = document.get('settings', {}).get(key, self.settings[key]) is True
        if 'rng' in document:
            version, values, gauss = document['rng']
            self.rng.setstate((version, tuple(values), gauss))

    def save(self):
        atomic_json(self.data / 'state.json', {'state': self.state, 'settings': self.settings,
                    'source_sha256': self.source_hash, 'rng': self.rng.getstate()})

    def receipt(self, action, success, detail):
        self.code.outcome(self.state, action, success, detail)
        path = self.data / 'actions.jsonl'
        if path.exists() and path.stat().st_size > 512_000:
            os.replace(path, self.data / 'actions.previous.jsonl')
        with path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({'time': time.time(), 'tick': self.state['ticks'],
                'action': action, 'success': success, 'detail': detail,
                'source_sha256': self.source_hash}) + '\n')

    def drawing(self):
        colors = ('#b7b0d2', '#a6c5d1', '#bfc4d8', '#d3bbcf')
        color = self.rng.choice(colors)
        dots = ''.join(f'<circle cx="{self.rng.randrange(25,615)}" cy="{self.rng.randrange(25,380)}" r="8" fill="{color}" opacity="0.2"/>' for _ in range(20))
        return ('<svg xmlns="http://www.w3.org/2000/svg" width="640" height="440" viewBox="0 0 640 440">'
            '<rect width="640" height="440" rx="24" fill="#142337"/>' + dots +
            '<path d="M260 250 L155 290 L195 325 L285 285" fill="#8785a9" stroke="#433e59" stroke-width="4"/>'
            '<path d="M290 315 L286 350 L265 357 M286 350 L305 356 M353 315 L350 350 L330 357 M350 350 L370 357" stroke="#e4b182" stroke-width="6" fill="none"/>'
            f'<ellipse cx="320" cy="250" rx="95" ry="83" fill="{color}" stroke="#433e59" stroke-width="4"/>'
            '<ellipse cx="349" cy="268" rx="55" ry="58" fill="#ddd8ee"/>'
            '<ellipse cx="364" cy="201" rx="44" ry="40" fill="#85b4ae"/>'
            '<circle cx="371" cy="159" r="56" fill="#b8b3cf" stroke="#433e59" stroke-width="4"/>'
            '<path d="M419 153 L463 168 L420 179 Z" fill="#e5bd83" stroke="#433e59" stroke-width="4"/>'
            '<ellipse cx="396" cy="149" rx="13" ry="17" fill="#302c41"/><circle cx="394" cy="143" r="4" fill="white"/>'
            '<ellipse cx="288" cy="253" rx="63" ry="42" fill="#9290b5" stroke="#433e59" stroke-width="4"/>'
            '<path d="M247 260 Q285 293 324 262" stroke="#c2bedc" stroke-width="4" fill="none"/>'
            '<text x="320" y="408" text-anchor="middle" font-family="Segoe UI, sans-serif" font-size="20" fill="#e4f0f8">'
            f'a very important bird / {self.state["creations"] + 1}</text></svg>')

    def tick(self, event='', window=''):
        changed = bool(self.settings['windows'] and window and self.last_window and window != self.last_window)
        if self.settings['windows']:
            self.last_window = window
        result = self.code.step(self.state, {'event': event, 'random': self.rng.random(),
            'can_create': self.settings['create'], 'window_changed': changed,
            'phrase': self.language.practice(self.rng) if (self.state['ticks'] + 1) % 31 == 0 else ''})
        action = result['action']
        if action not in {'wander', 'rest', 'play', 'watch', 'inspect', 'draw', 'note', 'chirp'}:
            raise ValueError(f'Unsupported XC desktop action: {action}')
        self.last_action = action
        if result['say']:
            self.message = result['say']
        if action in ('draw', 'note'):
            try:
                content = self.drawing() if action == 'draw' else self.code.note(self.state)
                path = self.playground.create(action, content)
            except (OSError, ValueError) as exc:
                self.message = str(exc)
                self.receipt(action, False, str(exc))
            else:
                self.receipt(action, True, path.name)
                self.message = 'made you a drawing!' if action == 'draw' else 'left a tiny field note!'
                if self.settings['show_creations']:
                    self.open_last()
        elif action == 'inspect':
            count = len(self.playground.files())
            self.message = f'{count} treasures in my folder. all extremely valuable.'
            self.receipt(action, True, f'{count} creations')
        elif event:
            self.receipt(event, True, self.message)
        if self.state['ticks'] % 15 == 0 or event or action in ('draw', 'note'):
            self.save()
        return result

    def talk(self, message):
        reply = self.language.respond(message, self.rng)
        self.message = reply
        self.save()
        return reply

    def begin_chat(self, message):
        message = message.strip()
        if not message or len(message) > 4000 or not words(message):
            raise ValueError('Tell me something with words, up to 4,000 characters.')
        history = copy.deepcopy(self.language.data['history'])
        query = message
        if len(words(message)) < 7:
            previous = next((x['text'] for x in reversed(history) if x['role'] == 'You'), '')
            query += ' ' + previous[:300]
        fact = self.language.recall(message) or self.language.recall(query)
        self.language.observe(message, 'You', identity=True)
        self.language.data['turns'] += 1
        self.language.record('You', message)
        snapshot = {'name': self.name, 'friend': 'Pip' if self.name == 'Lonk' else 'Lonk',
                    'personality': self.personality, 'message': message, 'history': history,
                    'memories': self.state['memories'][-5:], 'facts': [fact] if fact else [],
                    'user_name': self.language.data['name'], 'energy': self.state['energy'],
                    'taught_reply': self.language.data['taught'].get(key(message))}
        self.save()
        return copy.deepcopy(snapshot)

    def finish_chat(self, reply, mode='local'):
        self.language.record(self.name, reply)
        self.language.data['history'][-1]['mode'] = mode
        self.message = reply
        self.save()

    def simple_reply(self, message):
        return self.language.respond(message, self.rng, learn=False)

    def meet(self, other):
        line = self.code.social(self.state, other)
        self.message = line
        self.save()
        return line

    def teach(self, prompt, reply):
        self.language.teach(prompt, reply)
        self.code.remember(self.state, 'You taught me a reply to ' + prompt[:80])
        self.save()

    def learn_document(self, document):
        result = self.language.learn_file(document)
        if not result['duplicate']:
            self.code.remember(self.state, 'I learned words from ' + document['name'][:180])
            self.message = result['message']
        self.save()
        return result

    def open_last(self):
        if not self.playground.last:
            files = self.playground.files()
            if files:
                self.playground.last = files[-1]
        self.playground.open_creation()
        self.receipt('open_creation', True, self.playground.last.name)


def foreground_title():
    user = ctypes.windll.user32
    user.GetForegroundWindow.restype = wintypes.HWND
    user.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
    buffer = ctypes.create_unicode_buffer(512)
    user.GetWindowTextW(user.GetForegroundWindow(), buffer, len(buffer))
    return buffer.value


def work_area():
    rect = wintypes.RECT()
    if ctypes.windll.user32.SystemParametersInfoW(48, 0, ctypes.byref(rect), 0):
        return rect.left, rect.top, rect.right, rect.bottom
    return 0, 0, 1280, 720


class Pet:
    WIDTH, HEIGHT = 244, 180

    def __init__(self, root, brain, flock=None):
        import tkinter as tk
        self.tk, self.root, self.brain = tk, root, brain
        self.flock = flock
        self.follow_peer = None
        self.follow_until = 0
        self.hold_until = 0
        self.last_bubble = ''
        self.paused = False
        self.drag = None
        self.moved = False
        self.panel = None
        self.chat_window = None
        self.frame = 0
        self.running = True
        self.mode = 'wander'
        self.mode_until = 0
        self.bubble_until = time.monotonic() + 12
        self.x, self.y = 0.0, 0.0
        self.tx, self.ty = 0.0, 0.0
        self.monitor_time = 0
        self.area = work_area()
        left, top, right, bottom = self.area
        self.x, self.y = (left + right - self.WIDTH) / 2, bottom - self.HEIGHT
        self.tx, self.ty = self.x, self.y
        root.title('Desktop Lonk XC' if brain.name == 'Lonk' else 'Desktop Pip XC')
        root.overrideredirect(True)
        root.attributes('-topmost', True)
        root.attributes('-transparentcolor', KEY)
        root.configure(bg=KEY)
        self.canvas = tk.Canvas(root, width=self.WIDTH, height=self.HEIGHT, bg=KEY, highlightthickness=0)
        self.canvas.pack()
        self.menu = tk.Menu(root, tearoff=False)
        for label, command in [(f'Talk to {brain.name}', self.talk),
                (f'Give {brain.name} files...', self.share_files), (f'Pet {brain.name}', lambda: self.interact('pet')),
                ('Give a snack', lambda: self.interact('feed')),
                ('Make me a drawing', lambda: self.interact('draw')),
                ('Write a field note', lambda: self.interact('note')),
                ('Open latest creation', lambda: self.perform(self.brain.open_last)),
                ('Open playground folder', lambda: self.perform(self.brain.playground.open_folder)),
                (f'{brain.name} controls and memories', self.controls), ('Pause / resume', self.toggle),
                ('Take a nap', lambda: self.interact('nap')), ('Quit both birds and save', self.close)]:
            self.menu.add_command(label=label, command=command)
        if flock:
            self.menu.add_separator()
            self.menu.add_command(label='Call my friend over', command=lambda: flock.visit(self))
            self.menu.add_command(label='Talk to my friend', command=lambda: flock.other(self).talk())
            self.menu.add_command(label='Pause / resume both birds', command=flock.toggle)
        self.canvas.bind('<ButtonPress-1>', self.press)
        self.canvas.bind('<B1-Motion>', self.move)
        self.canvas.bind('<ButtonRelease-1>', self.release)
        self.canvas.bind('<Button-3>', self.popup)
        self.canvas.bind('<Double-Button-1>', lambda event: self.talk())
        root.bind('<Escape>', lambda e: self.close())
        root.report_callback_exception = self.callback_error
        root.protocol('WM_DELETE_WINDOW', self.close)
        self.position()
        root.update_idletasks()
        self.no_activate()
        self.animate()
        self.pending_tick = root.after(1000, self.step)

    def no_activate(self):
        user = ctypes.windll.user32
        user.GetParent.argtypes = (wintypes.HWND,)
        user.GetParent.restype = wintypes.HWND
        hwnd = user.GetParent(self.root.winfo_id()) or self.root.winfo_id()
        get_style = user.GetWindowLongPtrW
        set_style = user.SetWindowLongPtrW
        get_style.argtypes = (wintypes.HWND, ctypes.c_int)
        get_style.restype = ctypes.c_ssize_t
        set_style.argtypes = (wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t)
        set_style.restype = ctypes.c_ssize_t
        # Tool window + no activation: roaming must not steal typing focus.
        set_style(hwnd, -20, get_style(hwnd, -20) | 0x08000000 | 0x00000080)

    def position(self):
        left, top, right, bottom = self.area
        self.x = max(left, min(self.x, right - self.WIDTH))
        self.y = max(top, min(self.y, bottom - self.HEIGHT))
        self.root.geometry(f'{self.WIDTH}x{self.HEIGHT}+{int(self.x)}+{int(self.y)}')

    def press(self, event):
        self.drag = (event.x_root - self.x, event.y_root - self.y)
        self.moved = False

    def move(self, event):
        if self.drag:
            self.x, self.y = event.x_root - self.drag[0], event.y_root - self.drag[1]
            self.tx, self.ty = self.x, self.y
            self.moved = True
            self.position()

    def release(self, event):
        self.drag = None
        if not self.moved:
            self.interact('pet')

    def popup(self, event):
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def perform(self, fn):
        try:
            fn()
        except Exception as exc:
            self.brain.message = str(exc)
        self.bubble_until = time.monotonic() + 8

    def interact(self, event):
        self.perform(lambda: self.apply(self.brain.tick(event)))
        self.refresh_panel()

    def apply(self, result):
        if result['action'] != 'wander':
            self.mode = result['action']
            self.mode_until = time.monotonic() + (3 if self.mode == 'play' else 7)
            if self.brain.message != self.last_bubble:
                self.last_bubble = self.brain.message
                self.bubble_until = time.monotonic() + 8
        elif time.monotonic() >= self.mode_until:
            self.mode = 'wander'

    def step(self):
        if not self.running:
            return
        try:
            if not self.paused:
                title = foreground_title() if self.brain.settings['windows'] else ''
                self.apply(self.brain.tick(window=title))
            self.refresh_panel()
        except Exception as exc:
            self.paused = True
            self.brain.message = f'Paused: {exc}'
            self.bubble_until = time.monotonic() + 60
            self.log_error()
        self.pending_tick = self.root.after(1000, self.step)

    def animate(self):
        if not self.running:
            return
        self.frame += 1
        now = time.monotonic()
        if now - self.monitor_time > 5:
            self.area = work_area()
            self.monitor_time = now
        following = self.follow_peer is not None and now < self.follow_until
        if following:
            peer = self.follow_peer
            side = -1 if self.brain.name == 'Lonk' else 1
            left, top, right, bottom = self.area
            desired = peer.x + side * 115
            if desired < left or desired > right - self.WIDTH:
                desired = peer.x - side * 115
            self.tx, self.ty = desired, peer.y
        if not self.paused and not self.drag and now >= self.hold_until and (following or self.mode in ('wander', 'play')):
            dx, dy = self.tx - self.x, self.ty - self.y
            distance = math.hypot(dx, dy)
            if distance < 4 and not following:
                left, top, right, bottom = self.area
                self.tx = random.uniform(left, max(left, right - self.WIDTH))
                self.ty = random.uniform(max(top, bottom - self.HEIGHT - 170), max(top, bottom - self.HEIGHT))
            elif distance >= 4:
                speed = min(distance, 3.0 if following else (2.0 if self.mode == 'wander' else 3.5))
                self.x += dx / distance * speed
                self.y += dy / distance * speed
        self.position()
        self.draw()
        self.pending_frame = self.root.after(40, self.animate)

    def draw(self):
        c = self.canvas
        c.delete('all')
        asleep = self.mode == 'rest'
        lively = not self.paused and not asleep
        bob = math.sin(self.frame / 5) * (5 if self.mode == 'play' else 2) if lively else 0
        y = 110 + bob
        flap = math.sin(self.frame / 3) * 7 if self.mode in ('play', 'chirp') and lively else 0
        step = math.sin(self.frame / 3) * 3 if lively and self.mode == 'wander' else 0
        ink, feather, light = '#433e59', '#aaa6c7', '#ddd8ee'
        c.create_oval(81, 162, 169, 169, fill='#35404f', outline='')
        # Tail feathers behind the plump pigeon body.
        c.create_polygon(101, y + 17, 69, y + 26, 78, y + 42, 114, y + 35,
                         fill='#8785a9', outline=ink, width=2, tags=('bird', 'tail'))
        c.create_line(78, y + 30, 104, y + 28, fill='#bdb8d6', width=2)
        c.create_line(80, y + 36, 106, y + 31, fill='#bdb8d6', width=2)
        # Tiny orange legs and toes.
        for x, lift in ((111, step), (139, -step)):
            c.create_line(x, y + 38, x - 1, y + 52 + lift, fill='#ce986f', width=3)
            c.create_line(x - 9, y + 55 + lift, x - 1, y + 51 + lift, x + 7, y + 55 + lift,
                          fill='#e4b182', width=3, capstyle='round', tags='feet')
        c.create_oval(90, y - 13, 162, y + 49, fill=feather, outline=ink, width=2, tags=('bird', 'body'))
        c.create_oval(109, y + 5, 157, y + 43, fill=light, outline='')
        # Iridescent collar and round little head.
        c.create_oval(123, y - 6, 159, y + 20, fill='#85b4ae', outline='')
        c.create_arc(123, y - 5, 160, y + 22, start=205, extent=130, style='arc', outline='#b998cc', width=5)
        c.create_oval(114, y - 41, 163, y + 7, fill='#b8b3cf', outline=ink, width=2, tags='head')
        c.create_line(130, y - 37, 125, y - 49, 137, y - 42, 141, y - 49,
                      smooth=True, fill='#b8b3cf', width=4, capstyle='round')
        # Clearly bird-shaped beak, with a pale cere.
        c.create_polygon(158, y - 21, 180, y - 13, 159, y - 7,
                         fill='#e5bd83', outline=ink, width=2, tags=('bird', 'beak'))
        if self.mode == 'chirp' and self.frame % 12 < 6:
            c.create_line(161, y - 13, 177, y - 13, fill=ink, width=2)
        c.create_oval(154, y - 24, 163, y - 17, fill='#e7dfeb', outline='')
        blink = self.frame % 110 in (0, 1, 2)
        if asleep or blink:
            c.create_line(144, y - 25, 152, y - 24, fill=ink, width=3, capstyle='round')
        else:
            c.create_oval(141, y - 32, 155, y - 16, fill='#f1d3ac', outline='')
            c.create_oval(144, y - 30, 153, y - 18, fill='#302c41', outline='')
            c.create_oval(146, y - 29, 149, y - 25, fill='white', outline='')
        c.create_oval(137, y - 10, 147, y - 5, fill='#dca7bb', outline='')
        # Wing with layered feather marks; flaps when happy or talking.
        c.create_oval(89, y + flap, 132, y + 32 + flap, fill='#9290b5', outline=ink, width=2, tags=('bird', 'wing'))
        c.create_arc(93, y + 5 + flap, 125, y + 27 + flap, start=195, extent=145, style='arc', outline='#c2bedc', width=2)
        c.create_arc(95, y + 10 + flap, 120, y + 28 + flap, start=195, extent=135, style='arc', outline='#c2bedc', width=2)
        if self.mode == 'play' and not self.paused:
            c.create_text(188, y - 38, text='♥', fill='#ef9cb6', font=('Segoe UI', 18))
        if asleep:
            c.create_text(187, y - 32, text='z z', fill='#c7b6ee', font=('Segoe UI', 12))
        if self.brain.name == 'Pip':
            palette = {'#aaa6c7': '#e5c28c', '#ddd8ee': '#fff0c9', '#b8b3cf': '#ead1a3',
                       '#8785a9': '#c39a69', '#9290b5': '#cda574', '#c2bedc': '#f2d9af',
                       '#85b4ae': '#dca97e', '#b998cc': '#e6bc91', '#433e59': '#6e5343'}
            for item in c.find_all():
                for option in ('fill', 'outline'):
                    try:
                        old = c.itemcget(item, option)
                        if old in palette:
                            c.itemconfigure(item, **{option: palette[old]})
                    except self.tk.TclError:
                        pass
        c.create_text(124, 174, text=self.brain.name, fill='#edd8b6' if self.brain.name == 'Pip' else '#d7ceec', font=('Segoe UI', 8, 'bold'))
        if time.monotonic() < self.bubble_until or self.paused:
            c.create_polygon(112, 49, 123, 60, 133, 49, fill='#172936', outline='')
            c.create_rectangle(8, 4, 236, 51, fill='#172936', outline='#b8afd2', width=1)
            message = self.brain.message
            if len(message) > 105:
                message = message[:102] + '…'
            c.create_text(122, 27, text='Paused · right-click to resume' if self.paused else message,
                          width=211, fill='#edf5ed', font=('Segoe UI', 9), justify='center')

    def toggle(self):
        self.paused = not self.paused
        self.brain.message = 'back to extremely important business'
        self.bubble_until = time.monotonic() + 6
        self.refresh_panel()

    def talk(self):
        from pet_chat import Chat
        if self.chat_window is None:
            self.chat_window = Chat(self)
        else:
            self.chat_window.show()

    def share_files(self):
        self.talk()
        self.chat_window.choose_files()

    def controls(self):
        if self.panel and self.panel.winfo_exists():
            self.panel.lift()
            return
        tk = self.tk
        self.panel = panel = tk.Toplevel(self.root)
        panel.title(f'Your little {self.brain.name}')
        panel.geometry('440x590')
        panel.configure(bg='#142337')
        panel.attributes('-topmost', True)
        tk.Label(panel, text=f'{self.brain.name} · a small desktop life', bg='#142337', fg='#92e6b9',
                 font=('Segoe UI', 18, 'bold')).pack(pady=(18, 8))
        tk.Button(panel, text=f'Talk to {self.brain.name} / share files', command=self.talk, padx=16, pady=8).pack(pady=6)
        self.stats = tk.StringVar()
        tk.Label(panel, textvariable=self.stats, bg='#142337', fg='white', font=('Segoe UI', 10)).pack(pady=6)
        for key, label in [('create', 'Make drawings and notes in my playground'),
                           ('windows', 'Notice active window titles (kept in RAM only)'),
                           ('show_creations', 'Open new creations when I make them')]:
            var = tk.BooleanVar(value=self.brain.settings[key])
            def change(k=key, v=var):
                self.brain.settings[k] = v.get()
                if k == 'windows' and not v.get():
                    self.brain.last_window = ''
                self.perform(self.brain.save)
            tk.Checkbutton(panel, text=label, variable=var, command=change, bg='#142337', fg='#e2edf5',
                           selectcolor='#294155', activebackground='#142337', activeforeground='white',
                           anchor='w').pack(fill='x', padx=20, pady=3)
        bar = tk.Frame(panel, bg='#142337')
        bar.pack(pady=10)
        for title, fn in [('Draw', lambda: self.interact('draw')), ('Snack', lambda: self.interact('feed')),
                          ('Pause / resume', self.toggle), ('Folder', lambda: self.perform(self.brain.playground.open_folder))]:
            tk.Button(bar, text=title, command=fn).pack(side='left', padx=4)
        self.memories = tk.Text(panel, bg='#203449', fg='#dce9ee', relief='flat', height=10,
                               wrap='word', font=('Segoe UI', 10), padx=12, pady=10)
        self.memories.pack(fill='both', expand=True, padx=20, pady=8)
        tk.Label(panel, text='Click to pet · drag to move · right-click for actions\nDouble-click your bird to talk and teach it words.',
                 bg='#142337', fg='#9eb8c8', font=('Segoe UI', 9)).pack(pady=8)
        tk.Button(panel, text='Quit and save', command=self.close).pack(pady=(0, 15))
        self.refresh_panel()

    def refresh_panel(self):
        if not self.panel or not self.panel.winfo_exists():
            return
        s = self.brain.state
        self.stats.set(f"Energy {s['energy']:.0f} / 100    Curiosity {s['curiosity']:.0f} / 100\n"
                       f"{s['affection']} head pats · {s['creations']} creations · {'paused' if self.paused else self.mode}")
        self.memories.configure(state='normal')
        self.memories.delete('1.0', 'end')
        self.memories.insert('end', '\n\n'.join(reversed(s['memories'])) or 'A new little life. No memories yet.')
        self.memories.configure(state='disabled')

    def log_error(self):
        with (self.brain.data / 'errors.log').open('a', encoding='utf-8') as stream:
            traceback.print_exc(file=stream)

    def callback_error(self, *info):
        self.paused = True
        self.brain.message = 'Paused after a hiccup. Right-click for controls.'
        with (self.brain.data / 'errors.log').open('a', encoding='utf-8') as stream:
            traceback.print_exception(*info, file=stream)

    def close(self):
        if self.flock:
            return self.flock.close()
        if self.chat_window and hasattr(self.chat_window, "cancel_reply"):
            self.chat_window.cancel_reply()
        try:
            self.brain.save()
        except Exception as exc:
            from tkinter import messagebox
            if not messagebox.askyesno('Could not save Lonk', f'{exc}\n\nQuit without saving?', parent=self.root):
                return
        self.running = False
        self.root.destroy()


def gui_smoke(data):
    import tkinter as tk
    brain = Brain(data, seed=42)
    brain.settings['local_chat'] = False
    root = tk.Tk()
    pet = Pet(root, brain)
    root.update()
    pet.interact('pet')
    pet.interact('draw')
    pet.controls()
    root.update()
    assert brain.state['affection'] == 1
    assert len(brain.playground.files()) == 1
    pet.toggle()
    assert pet.paused
    root.update()
    report = {'gui': 'PASS', 'xc_action': brain.last_action,
              'creation': brain.playground.files()[0].name, 'canvas_items': len(pet.canvas.find_all()),
              'transparent_color': str(root.attributes('-transparentcolor')), 'source_sha256': brain.source_hash}
    frozen_ticks = brain.state['ticks']
    frozen_position = (pet.x, pet.y)
    root.after(1150, root.quit)
    root.mainloop()
    assert brain.state['ticks'] == frozen_ticks
    assert (pet.x, pet.y) == frozen_position
    pet.toggle()
    pet.mode = 'wander'
    pet.tx = pet.x + 80
    root.after(1150, root.quit)
    root.mainloop()
    assert brain.state['ticks'] > frozen_ticks
    assert (pet.x, pet.y) != frozen_position
    assert not (brain.data / 'errors.log').exists()
    report['pause_and_resume'] = 'PASS'
    pet.talk()
    root.update()
    chat = pet.chat_window
    chat.entry.insert('1.0', 'My name is Robin.')
    chat.send()
    assert 'Robin' in chat.transcript.get('1.0', 'end')
    lesson = Path(data) / 'bird-lesson.txt'
    lesson.write_text('Nebula pears glow violet at midnight.', encoding='utf-8')
    chat.import_files([str(lesson)])
    deadline = time.monotonic() + 12
    while chat.busy and time.monotonic() < deadline:
        root.update()
        time.sleep(0.025)
    assert not chat.busy, 'file import timed out'
    chat.entry.insert('1.0', 'What color do nebula pears glow?')
    chat.send()
    assert 'violet' in chat.transcript.get('1.0', 'end')
    assert 'bird-lesson.txt' in chat.library.get('1.0', 'end')
    pet.draw()
    assert pet.canvas.find_withtag('beak')
    assert pet.canvas.find_withtag('wing')
    assert not (brain.data / 'errors.log').exists()
    report['chat_and_async_file_learning'] = 'PASS'
    report['bird_beak_and_wings'] = 'PASS'
    pet.close()
    resumed = Brain(data)
    assert resumed.state['affection'] == 1
    assert resumed.state['creations'] == 1
    assert resumed.language.data['name'] == 'Robin'
    assert 'violet' in resumed.talk('What color do nebula pears glow?')
    report['restart'] = 'PASS'
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=Path, default=DATA)
    parser.add_argument('--gui-smoke', action='store_true')
    parser.add_argument('--chat', action='store_true')
    args = parser.parse_args()
    if args.gui_smoke:
        with tempfile.TemporaryDirectory(prefix='lonk-gui-') as directory:
            print(json.dumps(gui_smoke(directory), indent=2))
        return
    import tkinter as tk
    from tkinter import messagebox
    root = tk.Tk()
    root.withdraw()
    kernel = ctypes.windll.kernel32
    kernel.CreateMutexW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
    kernel.CreateMutexW.restype = wintypes.HANDLE
    mutex = kernel.CreateMutexW(None, False, 'Local\\DesktopLonkXC-' + hashlib.sha256(str(args.data.resolve()).encode()).hexdigest()[:16])
    if not mutex:
        raise ctypes.WinError()
    if kernel.GetLastError() == 183:
        messagebox.showinfo('Desktop Lonk', 'Your Lonk is already running. Look near the bottom of the desktop.', parent=root)
        root.destroy()
        return
    try:
        from pet_flock import Flock
        flock = Flock(root, args.data, Brain, Pet)
        pet = flock.pets[0]
        root.deiconify()
        if args.chat:
            root.after(150, pet.talk)
        root.mainloop()
    except Exception:
        args.data.mkdir(parents=True, exist_ok=True)
        error = traceback.format_exc()
        (args.data / 'startup-error.log').write_text(error, encoding='utf-8')
        messagebox.showerror('Lonk could not start', error, parent=root)
        root.destroy()
    finally:
        kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel.CloseHandle(mutex)


if __name__ == '__main__':
    main()
