Generate the project technical specification from the banking specification template.

This is the skill behind Meta-Agent 1 (see `.claude/agents/spec-writer.agent.md`).

Steps:

1. Read `TASKS.md` in this folder to collect the required specification sections and the minimum set of pipeline agents.
2. Read `sample-transactions.json` record by record. Note, for each record, which validation, fraud, compliance, or settlement rule it will exercise. Rules in the spec must be traceable to real sample data.
3. Read the Banking-Specific Specification Template in `../homework-3/specification-TEMPLATE-example.md` and follow its section order.
4. Write `specification.md` with these sections, in this order:
   - **High-Level Objective** — one sentence.
   - **Mid-Level Objectives** — 4 to 5 concrete, testable requirements. Each must name a status, a file location, or a numeric threshold so a test can assert it.
   - **Implementation Notes** — decimal money handling (never `float`), ISO 4217 currency allow-list, audit trail fields (timestamp, agent name, transaction id, outcome), and the rule that account numbers are masked in all logs.
   - **Context** — beginning state (`sample-transactions.json`) and ending state (populated `shared/results/`, pipeline summary report, coverage at or above 90 percent).
   - **Low-Level Tasks** — one entry per pipeline agent, each using exactly this format:
     ```
     Task: [Agent Name]
     Prompt: "[Exact prompt you will give the code-generation agent]"
     File to CREATE: agents/[agent_name].py
     Function to CREATE: process_message(message: dict) -> dict
     Details: [What the agent checks, transforms, or decides]
     ```
5. Write `agents.md` with the project-specific behavioural contract: stack assumptions, non-negotiable banking rules, the shared message envelope, code style, testing expectations, security and PII constraints, how to handle uncertainty, and the definition of done.
6. Report back which sample transaction exercises which rule, so the spec can be sanity-checked against the data.

Constraints:

- Specify interfaces and behaviour, never implementation bodies.
- Every status and reason string must belong to a closed enumerated set defined in the spec.
- Mark assumptions with **[ASSUMED]**.
- Leave no template placeholders, no "TBD", no unfilled square brackets.
