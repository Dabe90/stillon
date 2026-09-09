# Demo video script (≤ 5 minutes)

Record a screen + voiceover. You do not need to be on camera. Aim for **4:00–4:30**.

Before you hit record:

1. `stillon reset` then `stillon serve`
2. Browser at http://127.0.0.1:8000, window ~1280px wide
3. Keep `.env` off screen. Desk date should read **2026-09-09**
4. Have `docs/architecture.svg` open in a second tab for the last beat
5. Prefer a **local** night run for the recording (`STILLON_USE_BEDROCK` unset) so it finishes in seconds. Say Nova is wired; do not wait on tokens in the take

---

### 0:00–0:40 — The problem

People do not lose SNAP, Medicaid, or LIHEAP because they became ineligible. They lose them because a recertification letter sat on the counter. A food-bank benefits desk already helped them enroll. Six months later the same desk is fishing notices out of grocery bags.

That work is repetitive. It is also high-stakes. Miss the drop date and the household is hungry, uninsured, or cold.

### 0:40–1:10 — Who it is for

StillOn is for the overnight shift that does not exist: Harbor Light Food Bank’s benefits desk in Columbus. One caseworker. A caseload of households already on benefits. Morning is when they walk in.

### 1:10–1:40 — Why it matters

This is not another resource finder. Finder tools help people get in. StillOn keeps them in. Procedural churn is how benefits actually end. The agent does the matching and the packet. A human only chooses when the file is incomplete, income changed, a signature is missing, or benefits already dropped.

### 1:40–3:30 — Working product (screen)

Show the empty morning board. Point at the copy: *You only see households that need a person.* No chat box.

Click **Run last night**. When it returns, point at the counts: quiet left asleep, ready packets, needs you.

Open one **Ready to file** PDF. Say: the agent drafted this overnight. No one was woken.

Go back. Click one **Needs you** card — Santos stale paystub is the cleanest story. Read the question out loud. Click **File the stale stub with a gap note**. Watch the card leave and, if a packet appears, open it.

Say: that click resumed the same Strands session. The model never submitted. Filing stays a human act.

Scroll the full caseload so judges see quiet rows that never entered the model.

### 3:30–4:10 — How it is built

Switch to `docs/architecture.svg`. Three columns:

1. Python owns facts (drop dates, freshness)
2. Strands does the work (tools, Nova or local model, AgentCore entrypoint)
3. Human only for judgment (interrupt, resume)

One sentence: *Deadlines are code. Judgment is the agent. Filing is an interrupt.*

### 4:10–4:30 — Close

Repo: github.com/Dabe90/stillon. Apache-2.0. Good Neighbor track. Agents for Humans.

Food, coverage, heat — kept on by paperwork that actually went in.

---

If a take runs long, cut the PDF open on the ready column. Never skip the interrupt click. That is the product.
