"""Durable overnight receipts: S3 Object Lock + DynamoDB. Packets do not live only in /tmp."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .clock import desk_date
from .config import RUNTIME
from .deadlines import active_notice
from .store import PACKETS_DIR, STORE

BUCKET = os.environ.get("STILLON_PACKET_BUCKET", "").strip()
TABLE = os.environ.get("STILLON_DESK_TABLE", "").strip()
REGION = os.environ.get("AWS_REGION", "us-east-2")
CDN = os.environ.get("STILLON_CDN_URL", "").strip().rstrip("/")


def parse_packet_name(name: str) -> tuple[str, str]:
    stem = Path(name).name
    if stem.endswith(".pdf"):
        stem = stem[:-4]
    parts = stem.split("-")
    if len(parts) < 5:
        raise ValueError(f"unrecognized packet name {name}")
    program = parts[-4].upper()
    household_id = "-".join(parts[:-4])
    return household_id, program


def rebuild_packet_bytes(name: str) -> bytes:
    """Deterministic PDF from the seed. Does not need AgentCore /tmp."""
    from .packet import build_packet

    household_id, program = parse_packet_name(name)
    hh = STORE.household(household_id)
    notice = active_notice(hh, program)
    if notice is None:
        raise FileNotFoundError(name)
    record = build_packet(hh, notice)
    path = PACKETS_DIR / f"{record.packet_id}.pdf"
    return path.read_bytes()


def packet_bytes(name: str) -> bytes:
    safe = Path(name).name
    local = PACKETS_DIR / safe
    if local.exists():
        return local.read_bytes()
    remote = _s3_get(f"static/packets/{safe}")
    if remote:
        return remote
    return rebuild_packet_bytes(safe)


def persist_packet(path: Path) -> str:
    key = f"static/packets/{path.name}"
    try:
        _s3_put(key, path.read_bytes(), "application/pdf", lock=False)
    except Exception:
        pass
    if CDN:
        return f"{CDN}/static/packets/{path.name}"
    return f"/static/packets/{path.name}"


def persist_run(board: dict[str, Any]) -> None:
    run = board.get("last_run") or {}
    run_id = run.get("run_id") or f"run-{desk_date().isoformat()}"
    body = json.dumps(board, default=str).encode("utf-8")
    _s3_put(f"audit/runs/{run_id}.json", body, "application/json", lock=True)
    _ddb_put(
        {
            "pk": "DESK#harbor-light",
            "sk": "BOARD#current",
            "run_id": run_id,
            "desk_date": board.get("desk_date"),
            "quiet": (board.get("counts") or {}).get("quiet"),
            "needs_you": (board.get("counts") or {}).get("needs_you"),
            "ready": (board.get("counts") or {}).get("ready"),
            "caseload": (board.get("counts") or {}).get("caseload"),
            "model_name": board.get("model_name"),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "board": json.dumps(board, default=str),
        }
    )


def persist_decision(household_id: str, choice: str, board: dict[str, Any]) -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    payload = {
        "household_id": household_id,
        "choice": choice,
        "desk_date": board.get("desk_date"),
        "at": stamp,
    }
    _s3_put(
        f"audit/decisions/{stamp}-{household_id}.json",
        json.dumps(payload).encode("utf-8"),
        "application/json",
        lock=True,
    )


def load_snapshot() -> dict[str, Any] | None:
    item = _ddb_get("DESK#harbor-light", "BOARD#current")
    if not item:
        return None
    raw = item.get("board")
    if isinstance(raw, str):
        return json.loads(raw)
    return None


def list_audit(limit: int = 12) -> list[dict[str, str]]:
    if not BUCKET:
        return []
    import boto3

    s3 = boto3.client("s3", region_name=REGION)
    resp = s3.list_objects_v2(Bucket=BUCKET, Prefix="audit/", MaxKeys=limit)
    rows = []
    for obj in reversed(resp.get("Contents") or []):
        rows.append(
            {
                "key": obj["Key"],
                "modified": obj["LastModified"].isoformat(),
                "lock": "COMPLIANCE 30d",
            }
        )
    return rows[:limit]


def _s3_put(key: str, body: bytes, content_type: str, lock: bool) -> None:
    if not BUCKET:
        return
    import boto3

    kwargs: dict[str, Any] = {
        "Bucket": BUCKET,
        "Key": key,
        "Body": body,
        "ContentType": content_type,
    }
    if lock:
        until = datetime.now(timezone.utc) + timedelta(days=30)
        kwargs["ObjectLockMode"] = "COMPLIANCE"
        kwargs["ObjectLockRetainUntilDate"] = until
    boto3.client("s3", region_name=REGION).put_object(**kwargs)


def _s3_get(key: str) -> bytes | None:
    if not BUCKET:
        return None
    import boto3
    from botocore.exceptions import ClientError

    try:
        resp = boto3.client("s3", region_name=REGION).get_object(Bucket=BUCKET, Key=key)
        return resp["Body"].read()
    except ClientError:
        return None


def _ddb_put(item: dict[str, Any]) -> None:
    if not TABLE:
        return
    import boto3

    boto3.client("dynamodb", region_name=REGION).put_item(
        TableName=TABLE,
        Item=_to_ddb(item),
    )


def _ddb_get(pk: str, sk: str) -> dict[str, Any] | None:
    if not TABLE:
        return None
    import boto3

    resp = boto3.client("dynamodb", region_name=REGION).get_item(
        TableName=TABLE,
        Key={"pk": {"S": pk}, "sk": {"S": sk}},
    )
    item = resp.get("Item")
    if not item:
        return None
    return {k: list(v.values())[0] for k, v in item.items()}


def _to_ddb(item: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in item.items():
        if value is None:
            continue
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            out[key] = {"N": str(value)}
        else:
            out[key] = {"S": str(value)}
    return out


def writable_packets_dir() -> Path:
    PACKETS_DIR.mkdir(parents=True, exist_ok=True)
    RUNTIME.mkdir(parents=True, exist_ok=True)
    return PACKETS_DIR
