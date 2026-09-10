# StillOn

**Harbor Light Food Bank’s overnight benefits desk.**  
A [Strands Agents](https://strandsagents.com/) agent that keeps households from losing SNAP, Medicaid, or LIHEAP because a recertification letter sat on the counter.

Built for the [AWS Agents for Humans](https://agentsforhumans.devpost.com/) hackathon · **Good Neighbor** track.  
Public repo: [github.com/Dabe90/stillon](https://github.com/Dabe90/stillon) · Apache-2.0

StillOn is not a chatbot. It works the caseload while the caseworker sleeps. In the morning they only see the households that need a human: a missing paystub, an income change, an unsigned last page, or benefits that already dropped.

Deadlines and document freshness are **Python**. Judgment (which gap is worth waking someone) is the **Strands agent**. Filing is a **Strands interrupt** — the model cannot submit on its own.

![StillOn architecture](docs/architecture.svg)

## Who it is for

A food bank or legal-aid benefits desk that already helps people enroll, then loses them six months later to paperwork. Harbor Light is a demo pantry in Columbus, Ohio. The twelve households are synthetic; the chore is real.

## What it does end to end

1. Ranks every enrollment by drop date (deterministic calendar).
2. Skips quiet cases.
3. For the rest, a Strands agent loads the file, matches evidence to the notice, and either **drafts a PDF packet** or **pauses** with a real question.
4. A caseworker answers in the morning board. The same agent session resumes and finishes the packet.

## Quick start

Python 3.11+. From this directory:

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -e ".[dev]"
stillon night                   # work the caseload in the terminal
stillon serve                   # morning board at http://127.0.0.1:8000
pytest
```

The first run uses a local Strands model provider (`NightDeskModel`) so you can demo without AWS. It still goes through the real `strands.Agent` loop, tools, and `BeforeToolCallEvent` interrupts.

## Live demo

**Try it:** [https://stillon-a5if.onrender.com](https://stillon-a5if.onrender.com)  
Click **Run last night**, then answer one **Needs you** card. First load on the free host can take a minute.

The board is FastAPI. Public hosts should set `STILLON_USE_BEDROCK=0` so judges do not need a Bedrock key. AgentCore remains `deploy/agentcore_app.py`.

## Amazon Bedrock

This account’s project region is **Ohio (`us-east-2`)**. Stay there. Do not chase N. Virginia on a Blank Slate signup.

1. Open Bedrock in Ohio (the URL will contain `region=us-east-2`).
2. Left nav → **Test → Playground**. Send a short prompt to **Amazon Nova Lite**. Skip Anthropic for now.
3. Left nav → **Discover → API keys**. Generate a key. Copy it locally — never commit it.
4. Copy `.env.example` to `.env` and set:

```
STILLON_USE_BEDROCK=1
AWS_REGION=us-east-2
STILLON_MODEL_ID=amazon.nova-lite-v1:0
AWS_BEARER_TOKEN_BEDROCK=paste-the-key-here
```

Then `stillon night` again. Tools and interrupts do not change. Caseworker buttons still come from Python so a messy model call cannot garble the board.

## AgentCore

`deploy/agentcore_app.py` wraps the same night desk with `BedrockAgentCoreApp`. The live Runtime is in Ohio (`us-east-2`):

`arn:aws:bedrock-agentcore:us-east-2:750390206396:runtime/StillOn_StillOn-C6Gf1qBQlK`

IAM-signed invoke (no chatbot):

```bash
agentcore invoke --prompt board
agentcore invoke --prompt night
```

Payloads are `{"action": "night"}`, `{"action": "board"}`, or `{"action": "decide", "household_id": "hh-santos", "choice": "accept_stale_paystub"}`. The model still cannot file.

Local loop:

```bash
pip install bedrock-agentcore
python deploy/agentcore_app.py
# POST /invocations  {"action": "night"}
```

Redeploy from a path with no spaces (Windows): `cd %USERPROFILE%\stillon` then `agentcore deploy -y`.

## Submit

Paste-ready Devpost copy is in [`docs/DEVPOST.md`](docs/DEVPOST.md). Record from [`docs/DEMO.md`](docs/DEMO.md). Publish [`docs/BUILDER.md`](docs/BUILDER.md) on [builder.aws.com](https://builder.aws.com) with the title as written (it contains **Agents for Humans**).

## Repository layout

```
stillon/           agent, tools, deadline engine, matching, night desk, UI API
web/static/        morning board
data/seed.json     Harbor Light caseload (frozen to 2026-09-09)
deploy/            AgentCore entrypoint + Dockerfile
docs/              architecture, Devpost, demo script, Builder Center draft
tests/             deadline, matching, interrupt, and option-normalization tests
```

## License

Apache License 2.0. See `LICENSE`.
