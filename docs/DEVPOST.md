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

Live: [https://stillon-a5if.onrender.com](https://stillon-a5if.onrender.com)

Fraser is quiet on the empty board (60 days, `deadlines.py`). Last night is already on the board, or the page runs it on AgentCore without a click. Answer one **Needs you** card. Open a Ready PDF.

Local:

```bash
pip install -e ".[dev]"
stillon serve
```

Architecture diagram: `docs/architecture.svg` (also rendered in the README).

## AWS Builder ID

Paste the Builder ID you used on builder.aws.com here before you submit. The Devpost form requires it.

## Project Story (paste into “About the project”)

### Inspiration

Food banks already help people enroll in SNAP, Medicaid, and LIHEAP. The part that still breaks is quieter: six months later a recertification letter sits on the counter, the drop date passes, and the household is hungry, uninsured, or cold. That is procedural churn, not a discovery problem.

I did not want another chatbot that finds a pantry. Those exist, and this hackathon is full of them. I wanted the overnight shift that does not exist — a desk that works the caseload while the caseworker sleeps and only wakes a human when a real decision is required.

Harbor Light is a demo pantry in Columbus, Ohio. The twelve households are synthetic. The chore is real.

### What it does

StillOn ranks every enrollment by drop date in Python. Quiet cases never enter the model. For households due in twelve days, or already flagged, a Strands agent loads the file, matches evidence to the notice, and either drafts a PDF packet or pauses.

In the morning the caseworker opens a board, not a prompt box. **Needs you** is two or three buttons. **Ready to file** is a silent PDF. A click resumes the same Strands session. Filing is an interrupt. The model cannot submit on its own.

### How I built it

The product is a harness around a small model, not a prompt with a UI.

- **Facts are code.** Drop dates, urgency bands, and paystub freshness live in `deadlines.py` and `matching.py`. The LLM does not invent a due date.
- **Judgment is the Strands agent.** Six tools: household file, match, draft packet, escalate, submit, priority queue. Overnight it may draft. It may not file.
- **Authority is a hook.** `CaseworkerGate` listens for `BeforeToolCallEvent` on `escalate_decision` and `submit_packet`. The paused session is stored and resumed after a button click.
- **The board is FastAPI + a static morning UI.** No chat input.
- **The model is swappable.** Local `NightDeskModel` for a demo with no AWS. Amazon Nova Lite in Ohio (`us-east-2`) when `STILLON_USE_BEDROCK=1`. Same tools. Same interrupts.
- **AgentCore** wraps the same `night` / `board` / `decide` loop in `deploy/agentcore_app.py`.

### Challenges I ran into

Blank Slate is not the classic console. The project region is Ohio, not N. Virginia, and chasing `us-east-1` wasted time. Nova Lite in the playground was the first model that actually answered. Short-lived Bedrock API keys meant the night desk had to keep working when the key expired — that is why the local model provider exists.

Nova sometimes stuffed the choice list into a single control labeled `options`. A caseworker cannot click JSON. I stopped trusting the model for buttons. Python policy now owns the two choices (stale stub, missing signature, income change, already dropped). The model can still write the question.

One bad tool call used to kill the whole night. Each household is now isolated. A failure parks that file and the rest of the caseload still runs.

The harder design challenge was saying no to a prompt box. A chat demo is easier to record and easier to lose on. StillOn only works if the morning board stays quiet.

### What I learned

Determinism is what this hackathon is scoring, not a longer feature list. Deadlines belong in Python. Interrupts belong in hooks. The model should pick the next tool, not invent policy.

I also learned that a neighbor agent is a caseload, not a personal assistant. If StillOn works, twelve families keep food, coverage, or heat they already earned. If it chats, they still drop.

### What's next

The morning board is live at the Render URL. Opening it already shows Fraser is quiet and, when needed, runs last night on AgentCore — no **Run last night** click required. EventBridge sweeps at 06:00 America/New_York. AgentCore Runtime: `arn:aws:bedrock-agentcore:us-east-2:750390206396:runtime/StillOn_StillOn-C6Gf1qBQlK`. Next is a real pantry: real notices, real drop dates, same rule — the model drafts, the human files.
