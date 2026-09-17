# Bundled XC runtime provenance

The seven application/runtime files in this directory come from
[probablyapigeon/TheLonks](https://github.com/probablyapigeon/TheLonks)
at commit [`c6a317c81dda41e6aab280eca371d800d92db07f`](https://github.com/probablyapigeon/TheLonks/tree/c6a317c81dda41e6aab280eca371d800d92db07f):

- `LonkWorld.xc`
- `lonk_engine.py`
- `lonk_language.py`
- `lonk_society.py`
- `xc_runtime.py`
- `xc_app_runtime.py`
- `xc_procedures.py`

They are vendored for reproducible, offline application loading. The original
simulation tests and XC language-extension documentation live in that repository.
`main.py` and `index.html` are the WET browser adapter; they use the same XC
simulation as the desktop release, with no online AI dependency.

When updating, copy all seven files from one tested upstream revision, update
this reference, and run WET's route tests. Saves are bound to the exact XC
source hash, so keep a browser export before changing source versions.
