# Public morning board. Uses the local Strands model so the live demo
# never needs a Bedrock key in the container.
FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml LICENSE README.md ./
COPY stillon ./stillon
COPY data ./data
COPY web ./web

RUN pip install --no-cache-dir .

ENV STILLON_DESK_DATE=2026-09-09
ENV STILLON_USE_BEDROCK=0
ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["sh", "-c", "stillon serve --host 0.0.0.0 --port ${PORT:-8000}"]
