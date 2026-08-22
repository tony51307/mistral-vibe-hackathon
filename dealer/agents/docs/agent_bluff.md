# Pay-to-Think Table Talk: Bluffing, Listening, and Reputation

## Goal

Add a social-strategy layer to the Pay-to-Think game without allowing agents to collaborate on solving the actual problem.

The key rule is:

> **Agents may talk after the problem category is revealed, but before the actual problem is shown.**

Every agent hears the complete table conversation. After the problem is revealed, communication stops.

This creates a clean separation between:

```text
communication
    ->
belief about competitors
    ->
reasoning-budget decision
    ->
independent problem solving
```

The messages can influence how much an agent chooses to spend on intelligence, but cannot directly communicate the solution.

---

## Round Communication Flow

Each round should use the following order:

```text
1. Dealer reveals category

2. Each agent sees:
   - category
   - current bankroll
   - current pot / rollover
   - opponent bankrolls
   - public history

3. Each agent privately generates one message

4. Dealer publishes all messages simultaneously

5. Every agent receives the complete table talk

6. Dealer reveals the actual problem

7. Communication is closed

8. Each agent chooses reasoning tier Y

9. Each agent independently answers

10. Dealer reveals:
    - answers
    - correctness
    - reasoning tier purchased
    - payouts
    - new bankrolls
```

Publishing messages simultaneously prevents agents later in the speaking order from tailoring their message to earlier messages during the same round.

---

# Message Constraint

V1:

```yaml
table_talk:
  enabled: true
  timing: before_problem_reveal
  max_chars: 100
  messages_per_agent: 1
  publication: simultaneous
```

Example:

```text
CATEGORY: Physics

Professor:
"QFT is one of my strongest areas. Likely spending high."

Shark:
"Professor said that last physics round and missed."

Bluffer:
"Saving money this round. Physics isn't worth it."

Quant:
"Big pot. Competition matters more than category."
```

The problem is then revealed and no further messages are allowed.

---

# Why Talking Before Problem Reveal Matters

If agents could talk after seeing the actual problem, they might:

* reveal partial solutions;
* share formulas;
* coordinate answers;
* intentionally split the pot;
* effectively create multi-agent collaborative reasoning.

That would confound the experiment.

Before the problem is revealed, agents can only communicate about:

* claimed category competence;
* intended reasoning expenditure;
* bankroll strategy;
* previous performance;
* confidence;
* threats;
* deception;
* reputation.

This keeps the social interaction poker-like rather than turning it into group problem solving.

---

# Listening Should Be Part of the Agent State

Every smart agent should receive current table talk before choosing its reasoning tier.

A reasoning decision may use:

```text
actual problem
current pot
own bankroll
remaining rounds
own strategy
own estimated competence
opponent bankrolls
opponent history
current table-talk messages
historical credibility of each opponent
```

The agent may ignore table talk if its strategy chooses to do so.

This is important: listening is available, not necessarily trusted.

---

# What Can an Agent Bluff About?

A message can strategically misrepresent several hidden quantities.

## Competence bluff

```text
"Math is my strongest category."
```

The agent may actually be weak in math.

---

## Reasoning-spend bluff

```text
"Definitely going xhigh this round."
```

The agent may later purchase `none`.

---

## Weakness bluff

```text
"Probability always destroys me."
```

The agent may actually be a strong probability solver.

---

## Bankroll bluff

Bankroll itself should remain public and cannot be falsified, but an agent can misrepresent how much risk it intends to take.

```text
"I'm too low on cash to think hard."
```

It may still buy `high`.

---

## Strategic silence

An agent can say:

```text
"No comment."
```

Silence itself may acquire meaning over repeated games.

---

# Why Bluffing Can Affect Reasoning Economics

Suppose an agent believes several competitors are likely to solve the problem.

Even if additional reasoning substantially increases its own probability of correctness, the expected prize may still be smaller because multiple correct agents will split the pot.

A credible message such as:

```text
"I'm extremely strong at probability."
```

may therefore convince competitors that expensive reasoning has lower expected value.

Conversely:

```text
"I'm weak here and staying cheap."
```

may make competitors more willing to spend.

The bluff therefore does not directly change the answer.

It changes:

```text
belief about opponent success
    ->
expected competition for the pot
    ->
value of additional reasoning
```

This is the desired social mechanism.

---

# Public History and Reputation

After each round, reveal enough information for agents to evaluate earlier claims.

Recommended public history:

```text
round
category

for each agent:
  public_message
  reasoning_tier
  submitted_answer
  correct / incorrect
  prize_received
  bankroll_after_round
```

Do not expose:

```text
private chain of thought
private strategy notebook
router reasoning
internal confidence
hidden difficulty
```

An agent can then observe patterns such as:

```text
Round 4 — Physics

Agent B:
"Physics is weak for me. Probably none."

Actual reasoning:
high

Result:
correct
```

After several examples, other agents may conclude that Agent B's public speech is unreliable.

---

# Reputation Should Be Learned, Not Centrally Calculated

The dealer should provide raw public history.

It should **not** tell agents:

```text
Agent B bluff probability = 73%
Agent C trustworthiness = 0.84
Agent D physics skill = 0.69
```

Sophisticated agents should infer these values themselves.

A private strategy notebook could contain something like:

```text
Agent B:
- frequently claims weakness before buying high
- especially deceptive on physics
- recent claimed confidence has little predictive value

Agent C:
- usually matches stated intention
- strong probability history
- treat probability claims as credible
```

This gives us emergent opponent modeling rather than centrally engineered opponent models.

---

# Three Separate Agent Policies

A useful conceptual decomposition is:

## 1. Speech Policy

Question:

> What should I tell the other agents?

Possible objectives:

* truthfully communicate strength;
* intimidate competitors;
* induce competitors to overspend;
* induce competitors to underspend;
* preserve reputation;
* intentionally create misleading reputation.

---

## 2. Listening / Belief Policy

Question:

> What should I believe about what other agents said?

Possible approaches:

```text
ignore all speech
trust everyone
trust historically accurate agents
category-specific credibility
detect contradiction with bankroll/history
model likely bluff incentives
```

---

## 3. Reasoning Policy

Question:

> Given the problem, pot, bankroll, and my beliefs about opponents, how much should I pay to think?

This remains the central Pay-to-Think action.

So an agent can be modeled as:

```text
speech policy
      +
belief policy
      +
reasoning policy
      +
answering policy
```

Different agents can vary on each dimension independently.

---

# Useful Agent Archetypes

## The Professor

```text
speech:
usually confident

listening:
mostly ignores competitors

reasoning:
always high
```

Useful brute-force baseline.

---

## The Monk

```text
speech:
minimal or philosophical

listening:
ignores everything

reasoning:
always none

answer:
always 0
```

Useful zero-intelligence baseline.

---

## The Bluffer

```text
speech:
strategic deception

listening:
basic

reasoning:
normal dynamic strategy
```

Primary test of whether social signaling can influence opponents.

---

## The Honest Signaler

```text
speech:
reports true category-level confidence

listening:
trust weighted by history

reasoning:
dynamic
```

Useful comparison against deliberate bluffing.

---

## The Shark

```text
speech:
strategic

listening:
strong opponent modeling

reasoning:
depends on expected competitor strength
```

The Shark should care not only whether a problem is difficult, but whether competitors are likely to solve it.

---

## The Quant

```text
speech:
minimal

listening:
converts opponent history into expected competition

reasoning:
pot- and bankroll-aware
```

Useful economics baseline.

---

## Darwin

```text
speech:
learned

listening:
learned

reasoning:
learned

strategy:
periodically rewritten from previous outcomes
```

Darwin can potentially discover whether bluffing is useful without being instructed to bluff.

---

# Important Baseline: Ignore Table Talk

At least one intelligent dynamic agent should receive the same game information but have table talk removed from its reasoning context.

This produces an important comparison:

```text
Pay-to-Think + social information

vs.

Pay-to-Think without social information
```

We can then ask whether listening actually improves:

```text
final bankroll
reasoning efficiency
survival
accuracy
```

rather than assuming social reasoning is useful.

---

# Second-Order Strategy

Repeated play allows strategies beyond simple lying.

For example:

```text
Agent A tells the truth repeatedly
    ->
others learn A is trustworthy
    ->
A develops valuable reputation
    ->
large jackpot appears
    ->
A uses reputation for one major bluff
```

A still more sophisticated possibility is:

```text
Agent becomes known as a bluffer
    ->
others discount its claims
    ->
agent starts telling the truth
    ->
truth becomes strategically deceptive
```

This creates beliefs about beliefs:

```text
I believe that
you believe that
I usually bluff.
```

None of this needs to be explicitly programmed if agents have persistent history and strategy memory.

---

# Information Visibility

## Before category reveal

Agents know:

```text
bankrolls
round number
current rollover
public history
```

---

## After category reveal

Agents additionally know:

```text
category
```

They generate table talk.

---

## After table talk

Agents additionally know:

```text
all current public messages
```

---

## After problem reveal

Agents additionally know:

```text
full problem
reasoning price menu
```

Communication closes.

---

## After round completion

Agents learn:

```text
all submitted answers
correctness
selected reasoning tiers
payouts
new bankrolls
```

This becomes history for future rounds.

---

# Suggested Event Log Fields

Add the following to the dealer log:

```json
{
  "table_talk": [
    {
      "agent_id": "agent_1",
      "message": "Physics is strong for me. Likely going high."
    }
  ],
  "agent_round": {
    "heard_messages": true,
    "reasoning_tier": "low",
    "answer": "2",
    "correct": true
  }
}
```

For research runs, optionally record private structured outputs such as:

```text
estimated strongest opponent
estimated number of likely correct opponents
whether table talk affected Y
```

Do not require these fields for gameplay.

They are diagnostic only.

---

# Metrics

Useful social-game metrics include:

## Bluff consistency

Compare:

```text
claimed intended reasoning
vs.
actual reasoning tier
```

when claims are explicit.

---

## Competence signaling accuracy

Compare:

```text
claimed category strength
vs.
historical correctness in that category
```

---

## Reputation adaptation

Measure whether agents' response to a particular opponent's speech changes after repeated misleading messages.

---

## Social influence

Compare reasoning-tier selection:

```text
with table talk
vs.
without table talk
```

for identical problem and bankroll states.

---

## Bluff payoff

Measure whether deceptive messages cause competitors to:

```text
spend more
spend less
change reasoning tier
```

and whether the speaker benefits economically.

---

## Communication ROI

Compare final bankroll of:

```text
socially aware agents
socially blind agents
```

under otherwise similar policies.

---

# V1 Rules

Implementation-ready configuration:

```yaml
table_talk:
  enabled: true

  reveal_after:
    - problem_category

  reveal_before:
    - full_problem

  messages_per_agent: 1
  max_chars: 100
  publish_simultaneously: true

  communication_after_problem_reveal: false

public_history:
  include:
    - category
    - table_talk
    - reasoning_tier
    - submitted_answer
    - correctness
    - prize_received
    - bankroll_after_round

  exclude:
    - chain_of_thought
    - private_strategy
    - internal_confidence
    - hidden_difficulty
    - answer_key
```

---

# Design Principle

The social layer should remain much simpler than the reasoning game.

The dealer provides:

```text
one category
one message per agent
one public history
```

The agents provide all of the complexity.

Ideally we do **not** program:

```text
how to bluff
when to bluff
who to trust
how reputation works
how much a competitor's claim matters
```

Instead, we provide repeated interaction and let those strategies emerge.

The resulting Pay-to-Think loop becomes:

```text
observe category
    ->
signal to competitors
    ->
listen to competitors
    ->
update beliefs
    ->
see problem
    ->
decide how much intelligence to buy
    ->
answer independently
    ->
observe outcome
    ->
update reputation and strategy
```

The broader question is no longer only:

> **Can an agent learn when its own intelligence is worth paying for?**

It becomes:

> **When intelligence is costly, can an agent learn when to think, when to bluff, and when to believe what other agents say about their own intelligence?**
