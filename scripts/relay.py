"""Local-only OpenAI-compatible relay. Endpoint and credentials are runtime-only.

Preserves tools, tool_choice, messages, response model, and reasoning parameters.
Never logs prompts or secrets. Never retries ambiguous billed upstream calls.
"""
import json
import os
from pathlib import Path
import threading
import time
import uuid

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI()
ALLOWED = {"model", "messages", "tools", "tool_choice", "temperature", "top_p",
           "max_tokens", "max_completion_tokens", "reasoning_effort", "seed",
           "parallel_tool_calls", "response_format", "stop", "stream"}
# Transient relay->upstream failure. Must not contain DAEDALUS spend words
# (see daedalus.core.llm.client._SPEND_REFUSED); usage of the failed call is unknown,
# which DAEDALUS records on its own as an unknown-cost attempt.
TRANSPORT_ERROR_MESSAGE = "Upstream transport failure ({}); usage unknown"


def payload(body):
    unknown = set(body) - ALLOWED
    if unknown:
        raise ValueError(f"Unsupported request fields: {sorted(unknown)}")
    if body.get("stream"):
        raise ValueError("Streaming is not supported by this research relay")
    out = dict(body)
    out["stream"] = False
    out.setdefault("model", "hy3")
    # No hidden effort default; every experiment must specify it itself.
    return out


_AUDIT_LOCK = threading.Lock()


def audit_record(relay_id, started, status, data=None, error=None, request=None):
    """Secret-free, prompt-free metadata only: timing, status, usage, finish reason."""
    record = {"relay_id": relay_id, "started_unix": round(started, 3),
              "latency_s": round(time.time() - started, 3), "status": status,
              "error_type": error}
    if request is not None:
        record.update({"n_messages": len(request.get("messages") or []),
                       "has_tools": bool(request.get("tools")),
                       "reasoning_effort": request.get("reasoning_effort"),
                       "max_tokens": request.get("max_tokens") or request.get("max_completion_tokens")})
    if isinstance(data, dict):
        usage = data.get("usage") or {}
        choices = data.get("choices") or [{}]
        record.update({"upstream_id": data.get("id"), "returned_model": data.get("model"),
                       "prompt_tokens": usage.get("prompt_tokens"),
                       "completion_tokens": usage.get("completion_tokens"),
                       "finish_reason": (choices[0] or {}).get("finish_reason")})
    return record


def _audit(record):
    path = os.environ.get("HY3_RELAY_AUDIT_LOG")
    if not path:
        return
    line = json.dumps(record, sort_keys=True)
    with _AUDIT_LOCK, open(path, "a", encoding="utf-8") as stream:
        stream.write(line + "\n")
        stream.flush()


@app.post("/v1/chat/completions")
async def chat(req: Request):
    relay_id, started = uuid.uuid4().hex, time.time()
    try:
        out = payload(await req.json())
    except ValueError as exc:
        _audit(audit_record(relay_id, started, 400, error="invalid_request"))
        return JSONResponse({"error": {"message": str(exc), "type": "invalid_request_error"}}, 400)
    _audit({**audit_record(relay_id, started, "started", request=out), "latency_s": 0.0})
    key = Path(os.environ["HY3_KEY_FILE"]).read_text().strip()
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(600, connect=20)) as client:
            response = await client.post(os.environ["HY3_UPSTREAM_URL"], json=out,
                                         headers={"Authorization": f"Bearer {key}"})
        data = response.json()
        _audit(audit_record(relay_id, started, response.status_code, data=data, request=out))
        # Return the true upstream model, usage, function calls, and finish reason.
        return JSONResponse(data, status_code=response.status_code)
    except (httpx.HTTPError, ValueError) as exc:
        _audit(audit_record(relay_id, started, 502, error=type(exc).__name__, request=out))
        # Wording matters: DAEDALUS treats any error text containing spend words
        # ("billing", "budget", "quota", "credit") as a permanent refusal and kills the
        # whole arm. A transport timeout is transient and must stay retryable.
        return JSONResponse({"error": {"message": TRANSPORT_ERROR_MESSAGE.format(type(exc).__name__),
                                       "type": "upstream_error"}}, 502)


@app.get("/v1/models")
async def models():
    return {"object": "list", "data": [{"id": "hy3", "object": "model"}]}


@app.get("/health")
async def health():
    return {"status": "ok", "bind": "loopback", "effort_default": None,
            "tools_preserved": True, "returned_model_preserved": True}


if __name__ == "__main__":
    for name in ("HY3_UPSTREAM_URL", "HY3_KEY_FILE"):
        if not os.environ.get(name):
            raise SystemExit(f"Supply {name} at runtime")
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("HY3_RELAY_PORT", "8743")),
                log_level="warning")
