Hackathon Proposal: Vibe AutoThink
One-line pitch
Vibe AutoThink automatically decides when an AI coding agent should spend more tokens thinking—using cheap consistency checks to reserve deep reasoning for difficult or risky decisions.
Problem
Users currently choose a fixed thinking level:
Low thinking is fast and cheap but can miss subtle problems.
High thinking is more reliable but wastes time and tokens on simple tasks.
The agent has no reliable way to decide when additional reasoning is worth its cost.
Solution
Add an auto thinking mode to Mistral Vibe.
For each meaningful decision, AutoThink:
Produces a cheap initial decision.
Checks that decision from another perspective.
Measures whether the two decisions agree.
Uses deeper reasoning only when they materially disagree or the action is high-risk.
Example:
Initial decision:
  Edit agent_loop.py directly

Second perspective:
  Inspect the app-server boundary first

Stability:
  LOW

AutoThink:
  Escalating from LOW → HIGH

Final decision:
  Add a per-call reasoning override through the session backend
The second perspective reveals that the initial answer may have overlooked an architectural constraint.
Why   showcases Vibe
The project exercises Vibe’s core capabilities:
Configurable Mistral reasoning levels
Typed, event-driven agent loop
Subagents and isolated sessions
Skills and agent profiles
Tool execution and repository inspection
Token and cost accounting
Textual UI
Scheduled evaluation loops
Durable experiment history
This is not merely a demo built beside Vibe—it adds a capability useful to every Vibe user.
User experience
Users select:
/thinking auto
During a task, Vibe displays:
◆ AutoThink: HIGH

Decision agreement: 1/2
Risk: high
Reason: architecture disagreement
Probe cost: 310 tokens
Estimated deep-thinking budget: 3,000 tokens
For straightforward work:
◆ AutoThink: LOW

Decision agreement: 2/2
Risk: low
Reason: stable decision
Tokens saved: ~2,700
Demo: The Reasoning Arena
Run three Vibe agents on identical coding tasks:
Agent
Policy
Fast
Always low thinking
Deep
Always high thinking
AutoThink
Dynamically chooses

Each agent works in an isolated Git worktree. Tasks include:
Fixing a subtle bug
Implementing a feature
Finding a security issue
Making an architecture-sensitive change
Repairing failing tests
The dashboard compares:
Tests passed
Quality score
Tokens consumed
Cost and latency
Deep-reasoning calls
Quality per 1,000 tokens
Cases where deeper thinking changed the decision
Target result
The goal is not to prove AutoThink always produces the best answer.
The target result is:
AutoThink retains most of the quality of always thinking while spending significantly fewer reasoning tokens.
For example:
Fast:       61% tasks solved — 20K tokens
Deep:       86% tasks solved — 92K tokens
AutoThink:  82% tasks solved — 48K tokens
Technical implementation
Core contribution
Add thinking = "auto"
Add ephemeral per-call thinking overrides
Implement a typed reasoning router
Add cheap decision-consistency probes
Combine disagreement, action risk, and remaining budget
Emit typed routing events
Display routing decisions in the TUI
Add telemetry and token accounting
Showcase layer
Fast, Deep, AutoThink, and Judge agents
A benchmark-runner skill
An MCP server for deterministic task grading
Worktree isolation
Scheduled benchmark runs
A generated experiment report
MVP
For the hackathon, limit the router to:
One cheap baseline decision
One cheap critical-perspective decision
Structured JSON outputs
Deterministic disagreement scoring
low → high escalation
Three to five curated coding tasks
A live comparison among the three agents
This is achievable while retaining a strong demo.
Stretch goals
Escalate after failed tests or repeated tool failures
Learn routing thresholds from previous benchmark runs
Add budgets such as Frugal, Balanced, and Quality
Route individual planning, tool, and verification steps separately
Schedule nightly regression evaluations
Generate an “intelligence spending report” for each session
Demo narrative
Most coding agents either think too little and make mistakes, or think deeply about everything and waste resources. Vibe AutoThink checks whether a decision is stable before paying for more intelligence. When two cheap perspectives disagree—or the action is risky—it thinks harder. Otherwise, it moves quickly. The result is an agent that treats reasoning as a resource and shows users exactly where their tokens went.
Why it can win
Clear problem every AI user understands
Visible and compelling live demo
Meaningful contribution to Vibe’s open codebase
Measurable cost-versus-quality result
Grounded in a research-inspired idea
Useful beyond the hackathon
Naturally showcases Mistral models and Vibe architecture

