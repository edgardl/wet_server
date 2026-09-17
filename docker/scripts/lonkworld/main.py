"""Request-local LonkWorld browser and deterministic simulation adapter."""
import json
from pathlib import Path
import tempfile

from flask import Response
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge
from lonk_engine import LonkWorld
from xc_app_runtime import XCApplication

HERE = Path(__file__).resolve().parent
MAX_BODY = 2 * 1024 * 1024


def error(message, status=400):
    return Response(json.dumps({"error": message}), status=status,
                    content_type="application/json")


def integer(value, name, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name} must be an integer from {low} to {high}")
    return value


def run(request):
    if request.method == "GET" and request.args.get("format") != "json":
        return Response(HERE.joinpath("index.html").read_text(encoding="utf-8"),
                        content_type="text/html; charset=utf-8")
    if request.method not in ("GET", "POST"):
        return error("Use GET or POST", 405)
    try:
        if request.content_length is not None and request.content_length > MAX_BODY:
            return error("World request exceeds 2 MiB", 413)
        # Limit reads even when Content-Length is absent on a streaming request.
        raw = request.stream.read(MAX_BODY + 1)
        if len(raw) > MAX_BODY:
            return error("World request exceeds 2 MiB", 413)
        body = json.loads(raw) if raw else {}
        if not isinstance(body, dict):
            raise ValueError("Request must be a JSON object")
        seed = integer(body.get("seed", 2026), "seed", 0, 2**32 - 1)
        steps = integer(body.get("steps", 0), "steps", 0, 5)
        message = body.get("message", "")
        if not isinstance(message, str) or len(message) > 500:
            raise ValueError("message must be text of at most 500 characters")
        target = body.get("target_uid")
        if target is not None and not isinstance(target, str):
            raise ValueError("target_uid must be text or null")
        controller = XCApplication(HERE / "LonkWorld.xc")
        logs = []

        def capture(*values, **kwargs):
            if len(logs) < 100:
                logs.append(" ".join(map(str, values))[:1000])

        controller.procedures.globals["print"] = capture
        if "world" in body or "world_json" in body:
            saved = body.get("world_json", body.get("world"))
            if isinstance(saved, str):
                saved = json.loads(saved)
            if not isinstance(saved, dict):
                raise ValueError("world must be a saved world object")
            if saved.get("source_hash") != controller.source_hash:
                raise ValueError("This world belongs to a different LonkWorld version")
            if saved.get("config") != controller.config:
                raise ValueError("Saved configuration does not match this LonkWorld version")
            integer(saved.get("max_population"), "max_population", 1,
                    int(controller.config.get("max_population", 20)))
            with tempfile.TemporaryDirectory(prefix="lonkworld-") as directory:
                path = Path(directory) / "world.json"
                path.write_text(json.dumps(saved, allow_nan=False), encoding="utf-8")
                world = LonkWorld.load(path, controller=controller)
        else:
            world = LonkWorld(controller=controller, seed=seed,
                              starting_population=int(controller.config.get("starting_population", 5)),
                              max_population=int(controller.config.get("max_population", 20)))
        if target is not None and not any(l.uid == target and l.alive for l in world.lonks):
            raise ValueError("target_uid must identify a living Lonk")
        if message.strip():
            world.player_say(message.strip(), target_uid=target)
        for _ in range(steps):
            world.world_tick()
        controller.validate_world(world)
        snapshot = world.to_dict()
        result = {"tick": world.tick, "population": len(world.lonks),
                  "source_hash": controller.source_hash, "world": snapshot,
                  "world_json": json.dumps(snapshot, allow_nan=False), "logs": logs}
        # Flask's default jsonify sorts mapping keys. Preserve save-file order:
        # the XC program can iterate mappings while consuming seeded randomness.
        return Response(json.dumps({"status": "success", "data": result}, allow_nan=False),
                        content_type="application/json")
    except RequestEntityTooLarge:
        return error("World request exceeds 2 MiB", 413)
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError, RecursionError, BadRequest) as exc:
        return error(f"Invalid world request: {exc}")
