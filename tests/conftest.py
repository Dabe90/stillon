import os

os.environ.setdefault("STILLON_DESK_DATE", "2026-09-09")
os.environ["STILLON_USE_BEDROCK"] = "0"
os.environ["STILLON_USE_AGENTCORE"] = "0"
os.environ.pop("STILLON_SWEEP_URL", None)
os.environ.pop("STILLON_AGENTCORE_ARN", None)
