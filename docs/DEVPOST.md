# Devpost paste

Public repo: https://github.com/Dabe90/stillon  
Track: **Good Neighbor Agents**  
License: Apache-2.0 (already on the GitHub About license field)

## Project name

StillOn

## Tagline / elevator (≤200 characters if the form is tight)

Harbor Light’s overnight benefits desk. A Strands agent works the SNAP / Medicaid / LIHEAP caseload while the caseworker sleeps, and only wakes a human for a real decision.

## Built with

- Strands Agents SDK (`Agent`, tools, `BeforeToolCallEvent` interrupts, file session resume)
- Amazon Bedrock (Amazon Nova Lite, `us-east-2`)
- Amazon Bedrock AgentCore Runtime (`deploy/agentcore_app.py`)
- Python 3.11+, FastAPI, ReportLab

## Text description (paste into Devpost)

StillOn is the overnight benefits desk at Harbor Light Food Bank, a demo pantry in Columbus, Ohio.

Households already qualified for SNAP, Medicaid, or LIHEAP still lose those benefits when a recertification letter sits on the counter. That is procedural churn, not a discovery problem. Resource-finders help people enroll. StillOn keeps them on.

Every night the desk ranks the caseload by drop date in Python. Quiet enrollments never enter the model. For households due in twelve days or already flagged, a Strands agent loads the file, matches documents to the notice, and either drafts a PDF packet or pauses. Filing is a Strands interrupt. The model cannot submit on its own.

In the morning the caseworker opens a board, not a chatbot. There is no prompt box. They see two columns: **Needs you** (two or three buttons) and **Ready to file** (silent PDFs). A click resumes the same Strands session and finishes the packet only when it is safe.

The twelve households are synthetic. The chore is real: food, coverage, and heat lost to paperwork that nobody filed.

## How it works (optional extra field)

1. `deadlines.py` and `matching.py` own drop dates and document freshness. The LLM does not invent a due date.
2. `stillon/agent.py` builds a Strands `Agent` with six tools. Overnight it may `draft_packet`. It may not `submit_packet`.
3. `CaseworkerGate` listens for `BeforeToolCallEvent` on `escalate_decision` and `submit_packet`. Buttons come from Python policy so a messy model call cannot garble the morning board.
4. FastAPI serves the morning board at `/`. `POST /api/decide/{id}` resumes the paused session.
5. Swap `NightDeskModel` for Amazon Nova Lite with `STILLON_USE_BEDROCK=1`. Same tools, same interrupts.

## What judges should click

```bash
pip install -e ".[dev]"
stillon serve
```

Open http://127.0.0.1:8000 → **Run last night** → answer one **Needs you** card → open a Ready PDF.

Architecture diagram: `docs/architecture.svg` (also rendered in the README).

## AWS Builder ID

Paste the Builder ID you used on builder.aws.com here before you submit. The Devpost form requires it.
