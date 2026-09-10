"""Public door to AgentCore. EventBridge runs this overnight; Render POSTs here too."""

from __future__ import annotations

import json
import os
import urllib.request

ARN = os.environ["STILLON_AGENTCORE_ARN"]
SESSION = os.environ.get("STILLON_RUNTIME_SESSION", "stillon-harbor-light-desk-2026-09-09")
SECRET = os.environ.get("STILLON_SWEEP_SECRET", "")
RENDER = os.environ.get("STILLON_RENDER_URL", "https://stillon-a5if.onrender.com")
REGION = os.environ.get("AWS_REGION", "us-east-2")


def _parse(raw) -> dict:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if hasattr(raw, "read"):
        raw = raw.read()
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8")
    text = str(raw).strip()
    if not text:
        return {}
    if text.startswith("data: "):
        parts = [ln[6:] for ln in text.splitlines() if ln.startswith("data: ")]
        text = parts[-1] if parts else text
    data = json.loads(text)
    return data if isinstance(data, dict) else {"value": data}


def _invoke(payload: dict) -> dict:
    import boto3

    client = boto3.client("bedrock-agentcore", region_name=REGION)
    response = client.invoke_agent_runtime(
        agentRuntimeArn=ARN,
        qualifier="DEFAULT",
        runtimeSessionId=SESSION,
        contentType="application/json",
        accept="application/json",
        payload=json.dumps(payload).encode("utf-8"),
    )
    return _parse(response.get("response"))


def _ping_render() -> None:
    try:
        urllib.request.urlopen(RENDER.rstrip("/") + "/api/health", timeout=25)
    except Exception:
        pass


def _payload_from_event(event: dict) -> dict:
    if event.get("requestContext"):
        raw = event.get("body") or "{}"
        if event.get("isBase64Encoded"):
            import base64

            raw = base64.b64decode(raw).decode("utf-8")
        body = json.loads(raw or "{}")
        path = (event.get("rawPath") or event.get("path") or "/").rstrip("/")
        if path.endswith("decide"):
            body.setdefault("action", "decide")
        elif path.endswith("board"):
            body.setdefault("action", "board")
        else:
            body.setdefault("action", "night")
        return body
    if event.get("ping"):
        return {"action": "ping"}
    if event.get("action"):
        return event
    return {"action": "night"}


def _authorized(event: dict) -> bool:
    if not event.get("requestContext"):
        return True
    if not SECRET:
        return True
    headers = {str(k).lower(): v for k, v in (event.get("headers") or {}).items()}
    return headers.get("x-stillon-sweep") == SECRET


def handler(event, _context):
    event = event or {}
    if event.get("requestContext", {}).get("http", {}).get("method") == "OPTIONS":
        return _http(200, {"ok": True})
    if not _authorized(event):
        return _http(403, {"ok": False, "error": "forbidden"})
    payload = _payload_from_event(event)
    action = payload.get("action") or "night"
    if action == "ping":
        _ping_render()
        return _http(200, {"ok": True, "ping": True})
    result = _invoke(payload)
    if action == "night":
        _ping_render()
    return _http(200, result)


def _http(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,X-StillOn-Sweep",
        },
        "body": json.dumps(body),
    }
