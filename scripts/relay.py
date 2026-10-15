"""Local-only OpenAI-compatible relay. Endpoint and credentials are runtime-only.

Preserves tools, tool_choice, messages, response model, and reasoning parameters.
Never logs prompts or secrets. Never retries ambiguous billed upstream calls.
"""
import os
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI()
ALLOWED = {"model", "messages", "tools", "tool_choice", "temperature", "top_p",
           "max_tokens", "max_completion_tokens", "reasoning_effort", "seed",
           "parallel_tool_calls", "response_format", "stop", "stream"}


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


@app.post("/v1/chat/completions")
async def chat(req: Request):
    try:
        out = payload(await req.json())
    except ValueError as exc:
        return JSONResponse({"error": {"message": str(exc), "type": "invalid_request_error"}}, 400)
    key = Path(os.environ["HY3_KEY_FILE"]).read_text().strip()
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(600, connect=20)) as client:
            response = await client.post(os.environ["HY3_UPSTREAM_URL"], json=out,
                                         headers={"Authorization": f"Bearer {key}"})
        data = response.json()
        # Return the true upstream model, usage, function calls, and finish reason.
        return JSONResponse(data, status_code=response.status_code)
    except (httpx.HTTPError, ValueError):
        return JSONResponse({"error": {"message": "Upstream transport failure; billing unknown",
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
