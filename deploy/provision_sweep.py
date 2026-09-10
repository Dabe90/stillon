"""Create the public Lambda door + EventBridge morning sweep. Idempotent."""

from __future__ import annotations

import io
import json
import os
import secrets
import time
import zipfile
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

REGION = os.environ.get("AWS_REGION", "us-east-2")
ACCOUNT = "750390206396"
FUNCTION = "stillon-sweep"
ROLE_NAME = "stillon-sweep-lambda"
ARN = os.environ.get(
    "STILLON_AGENTCORE_ARN",
    "arn:aws:bedrock-agentcore:us-east-2:750390206396:runtime/StillOn_StillOn-C6Gf1qBQlK",
)
SESSION = "stillon-harbor-light-desk-2026-09-09"
RENDER = "https://stillon-a5if.onrender.com"
SECRET_FILE = Path(__file__).resolve().parent / ".sweep-secret"
ROOT = Path(__file__).resolve().parents[1]


def _secret() -> str:
    if SECRET_FILE.exists():
        return SECRET_FILE.read_text(encoding="utf-8").strip()
    value = secrets.token_hex(16)
    SECRET_FILE.write_text(value + "\n", encoding="utf-8")
    return value


def _zip_lambda() -> bytes:
    source = Path(__file__).resolve().parent / "sweep_lambda.py"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(source, arcname="sweep_lambda.py")
    return buf.getvalue()


def _iam(iam):
    assume = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }
        ],
    }
    try:
        role = iam.get_role(RoleName=ROLE_NAME)["Role"]
    except ClientError:
        role = iam.create_role(
            RoleName=ROLE_NAME,
            AssumeRolePolicyDocument=json.dumps(assume),
            Description="StillOn public sweep to AgentCore",
        )["Role"]
        time.sleep(8)
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": ["bedrock-agentcore:InvokeAgentRuntime"],
                "Resource": [ARN, f"{ARN}/*"],
            },
            {
                "Effect": "Allow",
                "Action": [
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:ListBucket",
                    "s3:PutObjectRetention",
                ],
                "Resource": [
                    "arn:aws:s3:::stillon-harbor-light-750390206396",
                    "arn:aws:s3:::stillon-harbor-light-750390206396/*",
                ],
            },
            {
                "Effect": "Allow",
                "Action": [
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                    "dynamodb:Query",
                ],
                "Resource": "arn:aws:dynamodb:us-east-2:750390206396:table/stillon-desk",
            },
            {
                "Effect": "Allow",
                "Action": [
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                "Resource": "*",
            },
        ],
    }
    iam.put_role_policy(
        RoleName=ROLE_NAME,
        PolicyName="stillon-sweep",
        PolicyDocument=json.dumps(policy),
    )
    return role["Arn"]


def _function(lam, role_arn: str, secret: str) -> str:
    env = {
        "STILLON_AGENTCORE_ARN": ARN,
        "STILLON_RUNTIME_SESSION": SESSION,
        "STILLON_SWEEP_SECRET": secret,
        "STILLON_RENDER_URL": RENDER,
        "STILLON_PACKET_BUCKET": "stillon-harbor-light-750390206396",
        "STILLON_DESK_TABLE": "stillon-desk",
    }
    code = {"ZipFile": _zip_lambda()}
    try:
        lam.get_function(FunctionName=FUNCTION)
        lam.update_function_code(FunctionName=FUNCTION, ZipFile=code["ZipFile"])
        waiter = lam.get_waiter("function_updated")
        waiter.wait(FunctionName=FUNCTION)
        lam.update_function_configuration(
            FunctionName=FUNCTION,
            Timeout=120,
            MemorySize=512,
            Role=role_arn,
            Environment={"Variables": env},
            Handler="sweep_lambda.handler",
            Runtime="python3.12",
        )
        waiter.wait(FunctionName=FUNCTION)
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ResourceNotFoundException":
            raise
        lam.create_function(
            FunctionName=FUNCTION,
            Runtime="python3.12",
            Role=role_arn,
            Handler="sweep_lambda.handler",
            Code=code,
            Description="StillOn night desk public door to AgentCore",
            Timeout=120,
            MemorySize=512,
            Environment={"Variables": env},
        )
        lam.get_waiter("function_active").wait(FunctionName=FUNCTION)
    cfg = lam.get_function(FunctionName=FUNCTION)["Configuration"]
    return cfg["FunctionArn"]


def _url(lam) -> str:
    try:
        return lam.get_function_url_config(FunctionName=FUNCTION)["FunctionUrl"]
    except ClientError:
        created = lam.create_function_url_config(
            FunctionName=FUNCTION,
            AuthType="NONE",
            Cors={
                "AllowOrigins": ["*"],
                "AllowMethods": ["*"],
                "AllowHeaders": ["content-type", "x-stillon-sweep"],
                "MaxAge": 86400,
            },
        )
        for sid, action, extra in (
            ("FunctionURLAllowPublic", "lambda:InvokeFunctionUrl", {"FunctionUrlAuthType": "NONE"}),
            ("FunctionURLAllowInvokeFunction", "lambda:InvokeFunction", {}),
        ):
            try:
                lam.add_permission(
                    FunctionName=FUNCTION,
                    StatementId=sid,
                    Action=action,
                    Principal="*",
                    **extra,
                )
            except ClientError as exc:
                if exc.response["Error"]["Code"] != "ResourceConflictException":
                    raise
        return created["FunctionUrl"]


def _rule(events, lam, fn_arn: str, name: str, schedule: str, payload: dict) -> None:
    events.put_rule(
        Name=name,
        ScheduleExpression=schedule,
        State="ENABLED",
        Description=f"StillOn {name}",
    )
    events.put_targets(
        Rule=name,
        Targets=[
            {
                "Id": "lambda",
                "Arn": fn_arn,
                "Input": json.dumps(payload),
            }
        ],
    )
    sid = f"events-{name}"
    try:
        lam.add_permission(
            FunctionName=FUNCTION,
            StatementId=sid,
            Action="lambda:InvokeFunction",
            Principal="events.amazonaws.com",
            SourceArn=f"arn:aws:events:{REGION}:{ACCOUNT}:rule/{name}",
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ResourceConflictException":
            raise


def main() -> None:
    secret = _secret()
    iam = boto3.client("iam")
    lam = boto3.client("lambda", region_name=REGION)
    events = boto3.client("events", region_name=REGION)
    role_arn = _iam(iam)
    fn_arn = _function(lam, role_arn, secret)
    url = _url(lam)
    if not url.endswith("/"):
        url += "/"
    # 07:00 America/New_York weekdays in September (EDT = UTC-4)
    _rule(events, lam, fn_arn, "stillon-morning-night", "cron(0 11 ? * MON-FRI *)", {"action": "night"})
    _rule(events, lam, fn_arn, "stillon-keepwarm", "rate(10 minutes)", {"ping": True})
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from provision_aws import BUCKET, TABLE, provision

    surface = provision(url, secret)
    cdn = surface["cloudfront"]
    render = ROOT / "render.yaml"
    render.write_text(
        "services:\n"
        "  - type: web\n"
        "    name: stillon\n"
        "    runtime: python\n"
        "    plan: free\n"
        "    buildCommand: pip install -e .\n"
        "    startCommand: stillon serve --host 0.0.0.0 --port $PORT\n"
        "    envVars:\n"
        "      - key: STILLON_DESK_DATE\n"
        '        value: "2026-09-09"\n'
        "      - key: STILLON_USE_BEDROCK\n"
        '        value: "0"\n'
        "      - key: STILLON_USE_AGENTCORE\n"
        '        value: "1"\n'
        "      - key: STILLON_SWEEP_URL\n"
        f'        value: "{url}"\n'
        "      - key: STILLON_SWEEP_SECRET\n"
        f'        value: "{secret}"\n'
        "      - key: STILLON_AGENTCORE_ARN\n"
        f'        value: "{ARN}"\n'
        "      - key: STILLON_RUNTIME_SESSION\n"
        f'        value: "{SESSION}"\n'
        "      - key: STILLON_PACKET_BUCKET\n"
        f'        value: "{BUCKET}"\n'
        "      - key: STILLON_DESK_TABLE\n"
        f'        value: "{TABLE}"\n'
        "      - key: STILLON_CDN_URL\n"
        f'        value: "{cdn}"\n'
        "      - key: PYTHON_VERSION\n"
        '        value: "3.12.8"\n',
        encoding="utf-8",
    )
    print(json.dumps({"function_url": url, "function_arn": fn_arn, **surface}, indent=2))


if __name__ == "__main__":
    main()
