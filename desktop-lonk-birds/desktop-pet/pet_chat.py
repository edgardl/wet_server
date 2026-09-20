"""Conversation and explicit file-sharing UI for Desktop Lonk."""
from __future__ import annotations

from pathlib import Path
import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, ttk

from pet_documents import extract_document

BG, PANEL, TEXT, MUTED, MINT, LILAC = '#142337', '#203449', '#edf1f8', '#a7b7ca', '#a6e8ce', '#c7b6ee'


class Chat:
    def __init__(self, pet):
        self.pet, self.brain = pet, pet.brain
        self.events = queue.Queue()
        self.busy = False
        self.window = w = tk.Toplevel(pet.root)
        w.title('Talk to Lonk')
        w.geometry('640x680')
        w.minsize(530, 530)
        w.configure(bg=BG)
        w.protocol('WM_DELETE_WINDOW', w.withdraw)
        tk.Label(w, text='a little bird, learning your words', font=('Segoe UI', 19, 'bold'),
                 bg=BG, fg=LILAC).pack(anchor='w', padx=22, pady=(18, 4))
        self.summary = tk.StringVar()
        tk.Label(w, textvariable=self.summary, bg=BG, fg=MUTED, font=('Segoe UI', 10)).pack(anchor='w', padx=22, pady=(0, 12))
        notebook = ttk.Notebook(w)
        notebook.pack(fill='both', expand=True, padx=18)
        chat = tk.Frame(notebook, bg=BG)
        library = tk.Frame(notebook, bg=BG)
        words = tk.Frame(notebook, bg=BG)
        notebook.add(chat, text='Conversation')
        notebook.add(library, text='Shared files')
        notebook.add(words, text='Learned words')
        self.transcript = tk.Text(chat, bg=PANEL, fg=TEXT, wrap='word', relief='flat',
                                  font=('Segoe UI', 11), padx=15, pady=12, state='disabled')
        scroll = ttk.Scrollbar(chat, command=self.transcript.yview)
        self.transcript.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.transcript.pack(fill='both', expand=True, pady=(10, 0))
        self.transcript.tag_configure('You', foreground=MINT, font=('Segoe UI', 10, 'bold'))
        self.transcript.tag_configure('Lonk', foreground=LILAC, font=('Segoe UI', 10, 'bold'))
        self.library = tk.Text(library, bg=PANEL, fg=TEXT, wrap='word', relief='flat',
                              font=('Segoe UI', 10), padx=15, pady=12, state='disabled')
        self.library.pack(fill='both', expand=True, pady=10)
        self.word_list = tk.Text(words, bg=PANEL, fg=TEXT, wrap='word', relief='flat',
                                font=('Segoe UI', 11), padx=15, pady=12, state='disabled')
        self.word_list.pack(fill='both', expand=True, pady=10)
        entry_bar = tk.Frame(w, bg=BG)
        entry_bar.pack(fill='x', padx=18, pady=(12, 8))
        self.entry = tk.Text(entry_bar, height=3, bg=PANEL, fg=TEXT, insertbackground=MINT,
                             wrap='word', relief='flat', font=('Segoe UI', 11), padx=10, pady=9)
        self.entry.pack(side='left', fill='x', expand=True)
        self.entry.bind('<Return>', self.on_return)
        tk.Button(entry_bar, text='Send', command=self.send, bg=MINT, fg=BG,
                  relief='flat', padx=16, pady=14, font=('Segoe UI', 10, 'bold')).pack(side='left', padx=(8, 0))
        actions = tk.Frame(w, bg=BG)
        actions.pack(fill='x', padx=18, pady=(0, 8))
        self.files_button = tk.Button(actions, text='Give files…', command=self.choose_files, bg=PANEL, fg=TEXT, relief='flat', padx=13, pady=8)
        self.files_button.pack(side='left')
        tk.Button(actions, text='Teach a reply…', command=self.teach_dialog, bg=PANEL, fg=TEXT, relief='flat', padx=13, pady=8).pack(side='left', padx=8)
        tk.Button(actions, text='Practice my words', command=self.practice, bg=PANEL, fg=TEXT, relief='flat', padx=13, pady=8).pack(side='left')
        self.status = tk.StringVar(value='Try “my name is …” or tell me something about your day.')
        tk.Label(w, textvariable=self.status, bg=BG, fg=MUTED, font=('Segoe UI', 9), wraplength=590, anchor='w', justify='left').pack(fill='x', padx=20, pady=(0, 8))
        tk.Label(w, text='I learn phrases and recall passages locally. Files stay on your computer.',
                 bg=BG, fg=MUTED, font=('Segoe UI', 9)).pack(anchor='w', padx=20, pady=(0, 14))
        self.refresh()
        w.after(100, self.entry.focus_set)

    def show(self):
        self.window.deiconify()
        self.window.lift()
        self.entry.focus_set()
        self.refresh()

    def on_return(self, event):
        if event.state & 0x1:
            return None
        self.send()
        return 'break'

    def say(self, reply):
        self.pet.mode = 'chirp'
        self.pet.mode_until = time.monotonic() + 5
        self.brain.message = reply[:105] + ('…' if len(reply) > 105 else '')
        self.pet.bubble_until = time.monotonic() + 9
        self.refresh()

    def send(self):
        message = self.entry.get('1.0', 'end').strip()
        if not message:
            return
        try:
            reply = self.brain.talk(message)
        except Exception as exc:
            self.status.set(str(exc))
            return
        self.entry.delete('1.0', 'end')
        self.status.set('Learned from your words and saved our conversation.')
        self.say(reply)

    def practice(self):
        phrase = self.brain.language.practice(self.brain.rng)
        if not phrase:
            self.status.set('Give me a few words first. I learn from what you say and share.')
            return
        reply = 'Practicing my learned words: ' + phrase
        self.brain.language.record('Lonk', reply)
        self.brain.save()
        self.say(reply)

    def teach_dialog(self):
        dialog = tk.Toplevel(self.window)
        dialog.title('Teach Lonk a reply')
        dialog.configure(bg=BG)
        dialog.geometry('460x285')
        dialog.transient(self.window)
        tk.Label(dialog, text='When I say…', bg=BG, fg=TEXT).pack(anchor='w', padx=18, pady=(18, 5))
        prompt = tk.Entry(dialog, bg=PANEL, fg=TEXT, insertbackground=MINT, font=('Segoe UI', 11))
        prompt.pack(fill='x', padx=18, ipady=7)
        tk.Label(dialog, text='Lonk should reply…', bg=BG, fg=TEXT).pack(anchor='w', padx=18, pady=(12, 5))
        reply = tk.Entry(dialog, bg=PANEL, fg=TEXT, insertbackground=MINT, font=('Segoe UI', 11))
        reply.pack(fill='x', padx=18, ipady=7)
        error = tk.StringVar()
        tk.Label(dialog, textvariable=error, bg=BG, fg='#ffbbbb', wraplength=415).pack(padx=18, pady=6)
        def teach():
            try:
                self.brain.teach(prompt.get(), reply.get())
            except Exception as exc:
                error.set(str(exc))
                return
            dialog.destroy()
            self.say('coo! I will remember that reply.')
        tk.Button(dialog, text='Teach Lonk', command=teach, bg=MINT, fg=BG, padx=16, pady=7).pack()
        prompt.focus_set()

    def choose_files(self):
        paths = filedialog.askopenfilenames(parent=self.window, title='Give Lonk something to learn from',
            filetypes=[('Documents and text', '*.txt *.md *.pdf *.docx *.xc *.py *.js *.json *.csv'), ('All files', '*.*')])
        if paths:
            self.import_files(paths)

    def import_files(self, paths):
        if self.busy:
            self.status.set('I am still reading the last files. One little beak at a time.')
            return
        paths = list(paths)
        if len(paths) > 5:
            self.status.set('Choose up to five files at a time.')
            return
        self.busy = True
        self.files_button.configure(state='disabled')
        self.status.set('Reading the files you chose…')
        def worker():
            for path in paths:
                try:
                    self.events.put(('document', extract_document(path)))
                except Exception as exc:
                    self.events.put(('error', f'{Path(path).name}: {exc}'))
            self.events.put(('done', None))
        threading.Thread(target=worker, daemon=True, name='Lonk-document-reader').start()
        self.pet.root.after(80, self.poll)

    def poll(self):
        finished = False
        while True:
            try:
                kind, value = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == 'done':
                finished = True
            elif kind == 'error':
                self.brain.language.record('Lonk', 'I could not read ' + value)
                self.status.set(value)
            else:
                try:
                    result = self.brain.learn_document(value)
                    message = 'I already learned from that file.' if result['duplicate'] else result['message']
                    self.status.set(message)
                    self.say(message)
                except Exception as exc:
                    self.status.set(str(exc))
                    self.brain.language.record('Lonk', str(exc))
        self.refresh()
        if finished:
            self.busy = False
            self.files_button.configure(state='normal')
        else:
            self.pet.root.after(80, self.poll)

    @staticmethod
    def replace(widget, text):
        widget.configure(state='normal')
        widget.delete('1.0', 'end')
        widget.insert('end', text)
        widget.configure(state='disabled')

    def refresh(self):
        data = self.brain.language.data
        self.summary.set(f"{self.brain.language.vocabulary} words learned · {len(data['taught'])} taught replies · {len(data['files'])} shared files")
        self.transcript.configure(state='normal')
        self.transcript.delete('1.0', 'end')
        history = data['history'] or [{'role': 'Lonk', 'text': 'coo! I am your little bird. Tell me your name? You can give me files or teach me how to answer you.'}]
        for item in history:
            self.transcript.insert('end', item['role'] + '\n', item['role'])
            self.transcript.insert('end', item['text'] + '\n\n')
        self.transcript.configure(state='disabled')
        self.transcript.see('end')
        files = '\n\n'.join(f"{f['name']}\n{f['characters']:,} characters learned" + (' · beginning only' if f['truncated'] else '') for f in data['files'])
        self.replace(self.library, files or 'No files yet. Use Give files… to share text, Markdown, code, PDF, or DOCX.\n\nOnly chosen files are read. Scanned PDFs need OCR.\n\nThe library holds 40 files; recall retains the latest 240 passages.')
        top = sorted(data['words'].items(), key=lambda pair: (-pair[1], pair[0]))[:120]
        learned = 'Words I have heard, and how often:\n\n' + '    ·    '.join(f'{word} ({count})' for word, count in top)
        if data['taught']:
            learned += '\n\nReplies you taught me:\n\n' + '\n'.join(f'{a} → {b}' for a, b in data['taught'].items())
        self.replace(self.word_list, learned)