"""Tau adapter for the WET run(request) contract."""
import json
from pathlib import Path
from flask import Response
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge
from tau_engine import LIMIT, operate

HERE = Path(__file__).resolve().parent

def reply(body, status=200):
    return Response(json.dumps(body, allow_nan=False), status=status,
                    content_type="application/json")

def run(request):
    if request.method == "GET":
        return Response((HERE / "index.html").read_text(encoding="utf-8"),
                        content_type="text/html; charset=utf-8")
    if request.method != "POST":
        return reply({"error": "Use GET or POST"}, 405)
    if request.mimetype != "application/json":
        return reply({"error": "Use application/json"}, 415)
    try:
        if request.content_length is not None and request.content_length > LIMIT:
            return reply({"error": "Request exceeds 1 MB"}, 413)
        raw = request.stream.read(LIMIT + 1)
        if len(raw) > LIMIT:
            return reply({"error": "Request exceeds 1 MB"}, 413)
        return reply(operate(json.loads(raw)))
    except RequestEntityTooLarge:
        return reply({"error": "Request exceeds 1 MB"}, 413)
    except (ValueError, TypeError, KeyError, OverflowError, BadRequest) as exc:
        return reply({"error": str(exc)}, 400)
