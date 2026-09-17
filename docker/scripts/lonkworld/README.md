# LonkWorld XC for WET

Open `/lonkworld` to play in your browser. Lonks learn your words, develop their
own speech and thoughts, graduate through learning stages, form colonies, and
build multiple partnerships. Play advances one day at a time; select a Lonk to
inspect their feelings and language. Talk to everyone or choose a recipient.

Worlds are saved in browser localStorage after successful turns. Export/import
JSON to keep a backup or move a world. Imported worlds must match the bundled
XC source and configuration. There is no shared server world or account: each
request restores, advances, and returns the browser's complete world. The server
uses a temporary file only while validating a restored save, then removes it.

## Installation

The Docker build includes this directory automatically. The existing
`provisioning.sh` instead mounts `/home/wet_model/scripts` over `/app/scripts`.
For that deployment, copy this **entire directory**, including all runtime files,
to `/home/wet_model/scripts/lonkworld` on the host. Keep the files together when
updating. No Tk, display server, or additional Python packages are needed beyond
WET's Flask dependency. Do not run the desktop application in the web container.

## API

`GET /lonkworld` returns the browser; `GET /lonkworld?format=json` returns a new
world. `POST /lonkworld` accepts a JSON object:

```json
{"seed": 2026, "steps": 1, "message": "hello little moon", "target_uid": null}
```

Include `world_json` from the previous response to continue; omit it to start
fresh. Keep this authoritative JSON **string unchanged** during transport,
storage, and export. JavaScript and JSON libraries can reorder object keys,
which affects seeded simulation iteration. Parse a copy for display only.
The object-valued `world` response is a convenience for inspection; the server
also accepts it for clients that preserve mapping order exactly.
`steps` defaults to 0 and must be an integer from 0 to 5. `seed` is an unsigned
32-bit integer. `message` is optional text of at most 500 characters, delivered
before advancing. `target_uid` is null for everyone or a living Lonk's ID.
Request bodies are limited to 2 MiB. Validation errors use HTTP 400, oversized
bodies 413, unsupported routed methods 405. WET's response envelope is
`{"status":"success","data":{"world":{},"world_json":"...","tick":0,"population":5,"source_hash":"...","logs":[]}}`.

## Tests

From the repository root with `docker/requirements.txt` installed:

```sh
python -m unittest discover -s tests -v
```

Tests exercise WET's actual route loader, deterministic continuation, language
retention, request isolation, browser delivery, and malformed input rejection.
For an actual browser smoke on Windows with Node 24, Microsoft Edge, and the
repository `.venv` containing Flask, run `node tests/browser_smoke.mjs`.
`LONK_PYTHON` and `LONK_EDGE` can override executable paths. It opens an isolated
headless browser, checks teaching/stepping/reload persistence, writes ignored
screenshots and results under `tests/artifacts`, and closes its own processes.
The simulation source and Python interpreter originate in
[TheLonks](https://github.com/probablyapigeon/TheLonks); see the bundled provenance
file for the exact source revision.
