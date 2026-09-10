"""Invoke the Ohio AgentCore night desk from the public board."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

ARN_DEFAULT = "arn:aws:bedrock-agentcore:us-east-2:750390206396:runtime/StillOn_StillOn-C6Gf1qBQlK"
SESSION_DEFAULT = "stillon-harbor-light-desk-2026-09-09"
SWEEP_DEFAULT = "https://u5dz5vsg6k5ivvwp4j7ous3tpm0qvqkz.lambda-url.us-east-2.on.aws"
# Same value as Render / Lambda. Lets the public host hit AgentCore even if yaml env vars did not sync.
SECRET_DEFAULT = "de59d0fb483f88d5e5574f73bf92e3a4"
REGION = os.environ.get("AWS_REGION", "us-east-2")


def _on_render() -> bool:
    return os.environ.get("RENDER", "").strip().lower() in {"true", "1"}


def runtime_arn() -> str:
    return os.environ.get("STILLON_AGENTCORE_ARN", "").strip() or ARN_DEFAULT


def runtime_session() -> str:
    return os.environ.get("STILLON_RUNTIME_SESSION", "").strip() or SESSION_DEFAULT


def sweep_url() -> str:
    url = os.environ.get("STILLON_SWEEP_URL", "").strip().rstrip("/")
    if url:
        return url
    return SWEEP_DEFAULT if _on_render() else ""


def sweep_secret() -> str:
    secret = os.environ.get("STILLON_SWEEP_SECRET", "").strip()
    if secret:
        return secret
    return SECRET_DEFAULT if _on_render() else ""


def remote_enabled() -> bool:
    flag = os.environ.get("STILLON_USE_AGENTCORE", "").strip().lower()
    if flag in {"0", "false", "no"}:
        return False
    if flag in {"1", "true", "yes"}:
        return True
    if _on_render():
        return True
    return bool(sweep_url() or os.environ.get("STILLON_AGENTCORE_ARN", "").strip())


def invoke(payload: dict[str, Any]) -> dict[str, Any]:
    url = sweep_url()
    if url:
        return _http_invoke(url, payload)
    return _boto_invoke(payload)


def _read_body(raw: Any) -> dict[str, Any]:
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


def _http_invoke(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    secret = sweep_secret()
    if secret:
        headers["X-StillOn-Sweep"] = secret
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return _read_body(resp.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:400]
        raise RuntimeError(f"AgentCore sweep failed ({exc.code}): {detail}") from exc


def _boto_invoke(payload: dict[str, Any]) -> dict[str, Any]:
    import boto3

    client = boto3.client("bedrock-agentcore", region_name=REGION)
    response = client.invoke_agent_runtime(
        agentRuntimeArn=runtime_arn(),
        qualifier="DEFAULT",
        runtimeSessionId=runtime_session(),
        contentType="application/json",
        accept="application/json",
        payload=json.dumps(payload).encode("utf-8"),
    )
    stream = response.get("response")
    if hasattr(stream, "read"):
        return _read_body(stream.read())
    chunks: list[bytes] = []
    for chunk in stream or []:
        chunks.append(chunk if isinstance(chunk, (bytes, bytearray)) else str(chunk).encode())
    return _read_body(b"".join(chunks))
