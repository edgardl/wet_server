# Desktop Lonk XC — a little bird learning your words

A transparent Windows desktop bird that wanders, remembers, makes things, and
learns from your conversations and explicitly shared files.

## Talk and teach

Double-click the bird, or right-click and choose **Talk to Lonk**. Type in the
conversation window and press Enter (Shift+Enter adds a new line).

- Say **my name is Kiers**; Lonk remembers your name after restarting.
- Tell it things. Its word counts and phrase-transition frequencies update.
- Ask about a topic you shared. It recalls a relevant passage and names its source.
- **Teach a reply…** maps a phrase to your chosen response. Case and punctuation
  are ignored when matching a taught phrase. Teaching the same prompt updates it.
- **Practice my words** produces a short phrase from learned word transitions.
- The **Learned words** tab shows the counts and taught replies.
- The bird occasionally chirps learned phrases while wandering.

This is a small local associative learner, not a pretrained conversational LLM.
It uses counted words/transitions, explicit prompt/response associations, simple
name recognition, and lexical passage retrieval. It does not understand arbitrary
questions or invent answers when it cannot find a relevant memory. Its own replies
are not recycled into training. Conversation is typed; microphone input is not
part of this version.

## Give files

Use **Give files…** and choose up to five files at once. Text, Markdown, code,
UTF-8/UTF-16 text, text-based PDF, and DOCX are supported. Files are read locally,
never executed or uploaded. Scanned PDFs need OCR first. Encrypted PDFs must be
unlocked before sharing.

Each file is limited to 10 MB. Up to 45,000 characters / 20 PDF pages are learned;
partial reads are explicitly labeled. File extraction runs in a separate process
with a 20-second timeout so reading cannot freeze the pet. Duplicate files do not
inflate learning counts. The bounded library holds 40 file records, 4,000 words,
200 taught replies, the latest 240 passages, and 120 conversation messages.
Older passages can roll out even while a file remains listed in the library.
Original files are not modified, and no other folder is scanned.

## Desktop life

Click to pet, drag to move, right-click for snacks, drawing, notes, controls,
pause, and quit. The bird has a beak, wings, tail feathers, and animated feet.
It wanders around the primary monitor's work area without stealing typing focus.

By default it creates drawings or field notes in its own playground at most once
per 90 active seconds. Pausing stops autonomous decisions and walking; explicit
menu actions still work. **Open new creations** optionally opens its files in
your associated applications. Window-title awareness is also optional and off by
default; raw titles stay in RAM only. No arbitrary keystrokes, network access,
shell commands, or startup service are supplied to the pet.

## Files and implementation

Launch with the **Desktop Lonk XC** shortcut, or `pythonw desktop_pet.py`.
`--chat` opens the conversation window immediately.

Data is in `%LOCALAPPDATA%\DesktopLonkXC`:

- `state.json`: pet needs, memories, language counts, passages, chat, and settings.
- `Playground/`: SVG drawings and text notes (150-file cap; never auto-deleted).
- `actions.jsonl`: bounded desktop-action receipts.

Old pet saves acquire an empty language memory while preserving their existing
memories and needs. The installer/restart procedure keeps a pre-upgrade backup.

`DesktopLonk.xc` owns the pet's needs, memory reactions, autonomous action selection,
and when it chirps learned phrases. It uses the existing XC Procedures version 1
extension in `../desktop-lonkworld/xc_procedures.py`. The host supplies animation,
persistence, the chat UI, a local language-learning service (`pet_learning.py`),
and bounded document extraction (`pet_documents.py`). These are trusted local
programs; this is not a hostile-code sandbox or full draft XC 0.1 conformance.

Python 3.14 with Tk is already installed. PDF extraction uses vendored pypdf 6.10.0:

```
python -m pip install --target vendor -r requirements.txt
python -m unittest discover -s . -p "test_*.py" -v
python desktop_pet.py --gui-smoke
```

The smoke test uses disposable state and checks animation, pause/resume, drawing,
bird features, chat, asynchronous file learning, and restart recall.