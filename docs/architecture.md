# StillOn architecture

Harbor Light runs one overnight Strands agent per household that is close to a drop date. Quiet enrollments never enter the model.

```mermaid
flowchart TD
  subgraph overnight [Overnight]
    Mail[Mailroom notices + household file]
    Rank[Deadline engine in Python]
    Agent[Strands Agent]
    Tools[Tools: household / match / draft / escalate]
    Gate[CaseworkerGate interrupt]
    Mail --> Rank
    Rank -->|skip quiet| Quiet[Stay asleep]
    Rank -->|due in 12 days or flagged| Agent
    Agent --> Tools
    Tools -->|complete file| PDF[Packet PDF]
    Tools -->|real decision| Gate
  end

  subgraph morning [Morning board]
    UI[Caseworker UI]
    Gate -->|needs you| UI
    PDF -->|ready to file| UI
    UI -->|choice| Resume[Resume same session]
    Resume --> Agent
  end

  subgraph aws [AWS]
    Bedrock[Amazon Bedrock Nova]
    Core[Bedrock AgentCore Runtime]
    Agent -.-> Bedrock
    Core --> Agent
  end
```

## What the model is allowed to do

| Work | Owner |
|---|---|
| Drop dates, urgency bands, paystub freshness | `deadlines.py` / `matching.py` |
| Which tool to call next | Strands agent loop |
| Wake a human | `escalate_decision` via `BeforeToolCallEvent.interrupt` |
| File a packet | `submit_packet`, also gated. Night prompt forbids it |

## Why this is not a chatbot

The morning board has no prompt box. The agent already ran. The only inputs are the two or three options on a paused interrupt.
