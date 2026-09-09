# ARM64 runtime for Amazon Bedrock AgentCore.
FROM --platform=linux/arm64 python:3.12-slim

WORKDIR /app
COPY pyproject.toml LICENSE README.md ./
COPY stillon ./stillon
COPY data ./data
COPY web ./web
COPY deploy/agentcore_app.py ./agentcore_app.py

RUN pip install --no-cache-dir .

ENV STILLON_DESK_DATE=2026-09-09
ENV STILLON_USE_BEDROCK=1
ENV AWS_REGION=us-east-2
EXPOSE 8080

CMD ["python", "agentcore_app.py"]
