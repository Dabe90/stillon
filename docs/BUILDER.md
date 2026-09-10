# Builder Center post (paste on builder.aws.com)

**Title (must include the phrase):** Agents for Humans: a food-bank night desk that only wakes a human for judgment

**Hashtag:** #AgentsforHumans

Publish this as a public post on builder.aws.com before the Devpost deadline. You can submit more than one post; this is the one that covers the build.

---

StillOn is the overnight benefits desk at a demo food bank in Columbus. I built it for the AWS Agents for Humans hackathon, Good Neighbor track.

The repetitive task is not “find a program.” Households at Harbor Light already qualified for SNAP, Medicaid, or LIHEAP. They still fall off because a recertification notice sat on the counter. Caseworkers spend the morning reconstructing files. I wanted an agent that does that reconstruction at night and only pings a person when the file is not safe to send.

## What I refused to build

A chatbot. The brief says the agent should run in the background and surface for a real decision. A prompt box would have been easier to demo and easier to lose on. The morning board has two columns and no input field. Quiet households never appear as work.

## Where AWS actually sits

I signed up through Blank Slate. The project region is Ohio (`us-east-2`), not N. Virginia. Amazon Nova Lite in the Bedrock playground was the first model that answered. The night desk uses that same model through the Strands `BedrockModel` and a Bedrock API key in local env, never in git.

Deadlines and paystub freshness are Python. The Strands agent only decides which tool to call. `escalate_decision` and `submit_packet` are gated with `BeforeToolCallEvent.interrupt`. On resume, the same file session continues. That is the product, not a wrapper around a chat completion.

`deploy/agentcore_app.py` wraps the same `run_night` / `board` / `decide` loop with `BedrockAgentCoreApp`. The Runtime is live in Ohio: `arn:aws:bedrock-agentcore:us-east-2:750390206396:runtime/StillOn_StillOn-C6Gf1qBQlK`. That path is the night desk, not a second agent.

## What broke, and what I kept deterministic

Nova Lite sometimes stuffed the option list into a single control labeled `options`. A caseworker cannot click JSON. The interrupt hook now takes buttons from a Python policy that already knows the gap (stale stub, missing signature, income change, already dropped). The model can still write the question. It cannot invent the two choices on the board.

I also learned not to let one bad household kill the night. Each file is try/except’d so a tool failure parks that case and the rest of the caseload still runs.

## Why this is a neighbor agent

One caseworker at a pantry is a group of households, not a personal assistant. If StillOn works, twelve families keep food, coverage, or heat they already earned. If it chats, they still drop.

Code: https://github.com/Dabe90/stillon  
Apache-2.0. Clone it, run `stillon serve`, and click **Run last night**.
