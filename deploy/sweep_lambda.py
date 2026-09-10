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
        body = json.loads(raw or "{}") if raw else {}
        if not isinstance(body, dict):
            body = {}
        path = (event.get("rawPath") or event.get("path") or "/").rstrip("/")
        method = event.get("requestContext", {}).get("http", {}).get("method") or "POST"
        if path.endswith("/api/health") or path.endswith("health"):
            body["action"] = "ping"
        elif path.endswith("/api/board") or path.endswith("board"):
            body.setdefault("action", "board")
        elif path.endswith("/api/audit") or path.endswith("audit"):
            body["action"] = "audit"
        elif path.endswith("decide"):
            body.setdefault("action", "decide")
        elif "packets/" in path:
            body["action"] = "packet"
            body["name"] = path.rsplit("/", 1)[-1]
        elif path.endswith("/api/night") or path.endswith("night"):
            body.setdefault("action", "night")
        elif method == "GET":
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
    method = (event.get("requestContext", {}).get("http", {}).get("method") or "").upper()
    if method in {"GET", "HEAD", "OPTIONS"}:
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
        return _http(200, {"ok": True, "ping": True, "service": "stillon"})
    if action == "audit":
        return _http(200, _audit())
    result = _invoke(payload)
    if action in {"night", "board", "decide"}:
        _snapshot(result)
    if action == "night":
        _ping_render()
    if action == "packet":
        return _packet_http(result)
    return _http(200, result)


def _packet_http(result: dict) -> dict:
    import base64

    raw = result.get("pdf_b64") or ""
    if not raw:
        return _http(404, {"ok": False, "error": "missing packet"})
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/pdf",
            "Access-Control-Allow-Origin": "*",
        },
        "body": raw,
        "isBase64Encoded": True,
    }


def _snapshot(result: dict) -> None:
    board = result.get("board") if isinstance(result.get("board"), dict) else result
    if not isinstance(board, dict):
        return
    table = os.environ.get("STILLON_DESK_TABLE")
    bucket = os.environ.get("STILLON_PACKET_BUCKET")
    try:
        import boto3

        if table:
            counts = board.get("counts") or {}
            run = (board.get("last_run") or {}).get("run_id") or ""
            boto3.client("dynamodb", region_name=REGION).put_item(
                TableName=table,
                Item={
                    "pk": {"S": "DESK#harbor-light"},
                    "sk": {"S": "BOARD#current"},
                    "run_id": {"S": str(run)},
                    "quiet": {"N": str(counts.get("quiet") or 0)},
                    "needs_you": {"N": str(counts.get("needs_you") or 0)},
                    "caseload": {"N": str(counts.get("caseload") or 0)},
                    "board": {"S": json.dumps(board, default=str)[:350000]},
                },
            )
        if bucket and (board.get("last_run") or {}).get("run_id"):
            from datetime import datetime, timedelta, timezone

            run_id = board["last_run"]["run_id"]
            boto3.client("s3", region_name=REGION).put_object(
                Bucket=bucket,
                Key=f"audit/runs/{run_id}.json",
                Body=json.dumps(board, default=str).encode("utf-8"),
                ContentType="application/json",
                ObjectLockMode="COMPLIANCE",
                ObjectLockRetainUntilDate=datetime.now(timezone.utc) + timedelta(days=30),
            )
    except Exception:
        pass


def _audit() -> dict:
    bucket = os.environ.get("STILLON_PACKET_BUCKET")
    if not bucket:
        return {"ok": True, "objects": []}
    import boto3

    resp = boto3.client("s3", region_name=REGION).list_objects_v2(
        Bucket=bucket, Prefix="audit/", MaxKeys=12
    )
    rows = []
    for obj in reversed(resp.get("Contents") or []):
        rows.append({"key": obj["Key"], "modified": obj["LastModified"].isoformat(), "lock": "COMPLIANCE 30d"})
    return {"ok": True, "lock": "S3 Object Lock COMPLIANCE 30 days", "objects": rows}


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
