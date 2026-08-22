# Pay-to-Think Multi-Agent Economy — 2 to 8 Players

> **9–10 player extension:** The agent-roster layer extends the supported table size to 10 without changing the mechanism below. For 9 and 10 initial agents, fixed season `H` is `$27` and `$30`, and the normal opening pots are `$117` and `$130`. All other invariants remain unchanged.

## 1. Design Goal

The same game should work with anywhere from **2 to 8 autonomous agents** without changing the meaning of money or reasoning.

The core invariants are:

```text
X = $10                 fixed entry fee
S = $80                 starting bankroll per agent

Y:
  none   = $1
  low    = $2
  medium = $3
  high   = $5
  xhigh  = $9
```

Only the dealer contribution `H` scales with table size.

The V1 rule is:

```text
H = $3 * initial_number_of_agents
```

`H` is calculated once when the table is created and then remains **fixed for the entire season**.

It never changes based on:

```text
problem category
hidden difficulty
current reasoning expenditure
number of correct answers
individual bankroll
agent claims
```

This preserves the rule that the dealer provides no hidden difficulty information.

---

# 2. Table-Size Configuration

| Initial agents | S per agent |   X | H per round | Normal pot |
| -------------: | ----------: | --: | ----------: | ---------: |
|              2 |         $80 | $10 |          $6 |        $26 |
|              3 |         $80 | $10 |          $9 |        $39 |
|              4 |         $80 | $10 |         $12 |        $52 |
|              5 |         $80 | $10 |         $15 |        $65 |
|              6 |         $80 | $10 |         $18 |        $78 |
|              7 |         $80 | $10 |         $21 |        $91 |
|              8 |         $80 | $10 |         $24 |       $104 |

The normal pot is:

```text
normal_pot = N * X + H
```

Since:

```text
X = 10
H = 3N
```

this simplifies to:

```text
normal_pot = 13N
```

---

# 3. Why H Scales Linearly

The dealer injects:

```text
$3 per initial seat
```

This is close to the desired average reasoning expenditure:

```text
target average Y ~= $2.5 to $3.2 per agent per round
```

Therefore, before wealth transfer effects:

```text
dealer money creation ~= reasoning money destruction
```

for every table size.

This makes the economy approximately scale-neutral.

For example, if all agents solve an easy problem:

```text
2-player table:
pot = $26
each receives $13

8-player table:
pot = $104
each receives $13
```

An agent using `$1 / none` has approximately:

```text
-$10 entry
-$1 reasoning
+$13 prize

net = +$2
```

in either case.

The economic meaning of an easy shared win therefore does not change merely because more agents are sitting at the table.

---

# 4. Keep X and Y Constant

Do **not** scale reasoning prices with the number of players.

These must always mean the same thing:

```text
$1 -> none
$2 -> low
$3 -> medium
$5 -> high
$9 -> xhigh
```

An agent deciding whether `$9` of intelligence is worth buying should face the same personal cost in a 2-player game and an 8-player game.

Likewise:

```text
X = $10
```

should remain constant.

Otherwise it becomes difficult to distinguish:

```text
agent strategy changed
```

from:

```text
economic rules changed
```

when comparing experiments.

---

# 5. Keep Starting Bankroll Constant

Use:

```text
S = $80
```

for every agent regardless of table size.

This means every agent begins with:

```text
8 normal entry fees
```

and the same personal ability to purchase reasoning.

Do not use:

```text
S proportional to N
```

for V1.

Larger tables naturally produce larger prizes and greater wealth inequality. That is part of the multiplayer game rather than something that should immediately be normalized away.

---

# 6. Prize Scaling Is a Feature

For a normal non-rollover round:

```text
pot = 13N
```

If `k` agents answer correctly:

```text
winner_share = 13N / k
```

Examples for an 8-agent table:

```text
8 winners -> $13 each
4 winners -> $26 each
2 winners -> $52 each
1 winner  -> $104
```

This produces a useful property:

> The fewer competitors capable of solving the problem, the more valuable being correct becomes.

That is exactly where expensive reasoning should become interesting.

A very difficult question can therefore produce:

```text
rare correctness
+
large individual payout
+
strong incentive to buy intelligence
```

without the dealer explicitly labeling the question as difficult.

---

# 7. Table Size Changes the Game Naturally

Different `N` values should produce different strategic environments.

## 2 agents — Heads-Up

Characteristics:

```text
strong opponent modeling
table talk matters heavily
large effect from each opponent
frequent unresolved problems
frequent jackpots
high variance
```

Useful for:

```text
bluffing experiments
reputation experiments
agent-vs-agent strategy
```

---

## 3 agents — Small Table

Characteristics:

```text
still highly strategic
reasonable jackpot frequency
individual opponents remain easy to model
```

Useful for development and debugging.

---

## 4 agents — Canonical Baseline

This should remain the reference configuration.

```text
S = $80
X = $10
H = $12
normal pot = $52
```

It provides a good balance among:

```text
competition
reasoning economics
rollovers
reputation
runtime/API cost
UI readability
```

Use 4 agents for most controlled experiments.

---

## 5–6 agents — Live Demo Sweet Spot

This may be the most entertaining audience configuration.

There are enough agents for visibly different strategies to emerge:

```text
frugal agent
overthinker
category specialist
aggressive spender
bluffer
adaptive agent
```

while the table remains understandable.

Recommended hackathon live-demo size:

```text
4 to 6 agents
```

---

## 7–8 agents — Tournament Mode

Characteristics:

```text
large base pots
strong competition
more simultaneous winners
less frequent rollover
higher chance of one large wealth transfer
more complex reputation dynamics
```

This is useful for:

```text
stress testing
emergent strategy experiments
large multi-agent demonstrations
```

but requires a somewhat harder problem distribution.

---

# 8. Important Effect: Rollover Probability Changes With N

Suppose every agent independently has approximately probability `q` of solving a problem.

The probability that nobody solves it is:

```text
P(no winner) = (1 - q)^N
```

For example, if individual solve probability is about 30%:

| Agents | Approx. probability nobody solves |
| -----: | --------------------------------: |
|      2 |                               49% |
|      3 |                               34% |
|      4 |                               24% |
|      5 |                               17% |
|      6 |                               12% |
|      7 |                                8% |
|      8 |                                6% |

So simply running the same problem distribution with more agents makes rollovers much rarer.

This should **not** be corrected by changing H.

Instead, correct it through the hidden problem distribution.

---

# 9. Problem Distribution Should Scale With N

A useful target is approximately:

```text
10% to 20% of rounds unresolved
```

with roughly:

```text
15%
```

as a good initial target.

To produce approximately a 15% unresolved probability, the average per-agent solve probability needs to be roughly:

| Agents | Desired per-agent solve probability |
| -----: | ----------------------------------: |
|      2 |                                 61% |
|      3 |                                 47% |
|      4 |                                 38% |
|      5 |                                 32% |
|      6 |                                 27% |
|      7 |                                 24% |
|      8 |                                 21% |

These are **dealer calibration values only**.

Agents must never see them.

The important implication is:

> Larger tables should receive harder problem distributions.

For a 2-agent table, many medium problems can still produce jackpots.

For an 8-agent table, a problem that every agent solves with 50% probability will almost never roll over.

---

# 10. Recommended Distribution Policy

Do not select problems only by human labels such as `easy` or `hard`.

Once enough runs exist, estimate:

```text
observed solve rate by:
  problem
  model
  reasoning tier
```

Then the distributor can select an agenda whose expected overall solve rate is appropriate for the current number of agents.

A rough V1 fallback before enough empirical data exists:

```text
2–3 agents:
  relatively easier pool

4 agents:
  baseline distribution

5–6 agents:
  somewhat harder pool

7–8 agents:
  substantially harder pool
```

For example:

| Table size | Easy/trivial | Medium | Hard | Very hard |
| ---------- | -----------: | -----: | ---: | --------: |
| 2–3        |          40% |    35% |  20% |        5% |
| 4          |          30% |    30% |  25% |       15% |
| 5–6        |          20% |    30% |  30% |       20% |
| 7–8        |          15% |    25% |  35% |       25% |

Treat this only as bootstrap configuration.

Empirical solve rates should eventually replace these labels.

---

# 11. Do Not Reveal Distribution Adaptation

The agent receives:

```text
category
current pot
current bankroll
round number
public table talk
problem
reasoning menu
```

It must not receive:

```text
difficulty
expected solve rate
N-adjusted difficulty
problem-selection strategy
historical population accuracy
recommended reasoning tier
```

From the agent's point of view:

> The dealer simply asks questions.

The fact that the dealer uses a harder distribution for an 8-player table is invisible.

---

# 12. H Is Fixed by Initial Table Size

Define:

```text
N0 = number of agents when season begins
```

Then:

```text
H = 3 * N0
```

Keep this value for the entire season.

Example:

```text
8 agents start

H = $24
```

Later, only five agents remain:

```text
H is still $24
```

Do not reduce it to `$15`.

This is intentional for V1.

It produces a natural late-game accelerator:

```text
fewer survivors
+
same external task value
=
larger reward available per surviving competitor
```

It also prevents economic policy from changing whenever an agent is eliminated.

---

# 13. Late-Game Effect of Fixed H

Suppose an 8-agent season has fallen to two surviving agents.

The normal pot becomes:

```text
2 * $10 + $24 = $44
```

rather than the `$26` that a fresh two-agent game would have.

This means surviving late-game agents are competing for tasks whose dealer bounty was calibrated for the original tournament.

That creates:

```text
larger swings
stronger comeback opportunities
faster endgame
```

For a fixed 25-round hackathon game, this is desirable.

Do not introduce dynamic-H monetary policy in V1.

---

# 14. Show Hand Rules Are Independent of N

For every table size:

```text
if 0 < bankroll < X:
    agent may SHOW HAND
```

With:

```text
X = $10
```

the agent:

```text
stakes all remaining bankroll
buys no paid reasoning
uses base/no-thinking answer
```

If correct, it receives its normal share and can recover.

If incorrect, its bankroll remains zero and it is eliminated.

The rule does not change for larger tables.

---

# 15. Early Termination

If only one agent remains with positive bankroll:

```text
end season immediately
declare that agent winner
```

Do not continue letting one agent collect dealer contributions.

If every remaining agent reaches zero in the same unresolved Show Hand round:

```text
result = HOUSE_WIN
```

Record the unresolved pot and end the season.

This should be rare, but the implementation must define it.

---

# 16. Jackpot Rules Across Table Sizes

Normal pot:

```text
P0 = 13N
```

Unresolved rounds roll over completely:

```text
next_pot = rollover + new_entries + H
```

Examples:

### 4 agents

```text
normal:     $52
1 rollover: $104
2 rollover: $156
```

### 8 agents

```text
normal:     $104
1 rollover: $208
2 rollover: $312
```

Keep:

```text
max unresolved chain = 3
```

for the live demo.

A very large jackpot is allowed to create a dramatic wealth transfer.

That is part of the game.

---

# 17. Reasoning Affordability

Reasoning prices remain absolute.

Example:

```text
bankroll after entry = $4
```

The agent can afford:

```text
none   $1
low    $2
medium $3
```

but cannot afford:

```text
high   $5
xhigh  $9
```

This rule never changes based on table size.

A poorer agent has less access to intelligence.

That scarcity is an intentional part of the experiment.

---

# 18. Economy Health Should Be Measured Per Agent

Absolute money supply naturally increases with N.

Therefore compare tables using normalized metrics.

## Average reasoning spend

```text
mean_Y_per_active_agent
```

Target:

```text
$2.5 to $3.2
```

---

## Burn ratio

```text
burn_ratio = total_Y_burned / H
```

Useful interpretation:

```text
~1.0     approximately balanced
<0.7     inflationary / agents are very frugal
>1.3     deflationary / agents are reasoning aggressively
```

Do not react to a single round.

Use season averages.

---

## Money per initial seat

Track:

```text
(total bankroll + rollover) / N0
```

instead of comparing raw money supply.

---

## Rollover rate

Target roughly:

```text
10% to 20%
```

If an 8-agent table has almost no rollovers, increase problem difficulty rather than changing H.

---

## Reasoning distribution

A healthy initial target remains:

```text
none       25–35%
low        20–30%
medium     20–30%
high       10–20%
xhigh       2–8%
```

This target is independent of table size.

---

## Wealth concentration

For 5–8 agent games, also track:

```text
largest bankroll share
bankroll Gini coefficient
number of surviving agents
```

High inequality is not automatically a failure.

It becomes problematic only if one agent becomes economically unbeatable very early in most runs.

---

# 19. Recommended Table Modes

```yaml
table_modes:

  heads_up:
    agents: 2
    starting_bankroll: 80
    entry_fee: 10
    dealer_contribution: 6
    use_case:
      - opponent modeling
      - bluffing
      - reputation

  baseline:
    agents: 4
    starting_bankroll: 80
    entry_fee: 10
    dealer_contribution: 12
    use_case:
      - scientific baseline
      - A/B tests
      - economy calibration

  demo:
    agents: 6
    starting_bankroll: 80
    entry_fee: 10
    dealer_contribution: 18
    use_case:
      - hackathon live demo
      - emergent strategies
      - visible agent diversity

  tournament:
    agents: 8
    starting_bankroll: 80
    entry_fee: 10
    dealer_contribution: 24
    use_case:
      - stress test
      - multi-agent dynamics
      - large jackpots
```

---

# 20. Parameterized Implementation

The dealer should not hard-code separate economies.

Use:

```python
def build_economy(initial_agent_count):
    assert 2 <= initial_agent_count <= 8

    return {
        "initial_agents": initial_agent_count,
        "starting_bankroll": 80,
        "entry_fee": 10,
        "dealer_contribution": 3 * initial_agent_count,
        "reasoning_prices": {
            "none": 1,
            "low": 2,
            "medium": 3,
            "high": 5,
            "xhigh": 9,
        },
        "season_rounds": 25,
        "max_rollover_chain": 3,
    }
```

At season initialization:

```text
N0 = initial_agent_count
H = 3 * N0
```

After that:

```text
H must not change
```

even if agents are eliminated.

---

# 21. Recommended Experimental Protocol

When comparing agent reasoning strategies, hold constant:

```text
initial N
problem agenda
problem order
starting bankroll
X
H
Y
model version
random seed where possible
```

Then compare policies such as:

```text
Always None
Always High
Random Reasoning
Self-Reported Confidence Router
Perturbation Router
Autonomous Pay-to-Think Strategy
```

When comparing **different table sizes**, report results normalized per agent.

Do not interpret raw bankroll or raw total reasoning spend across different N directly.

---

# 22. V1 Economy Summary

The complete scaling rule is deliberately simple:

```text
2 <= N <= 8

S = $80 per agent

X = $10

H = $3 * initial N
and remains fixed for the season

Y:
  none   $1
  low    $2
  medium $3
  high   $5
  xhigh  $9

normal pot = $13 * active entries
             plus the fixed H relationship at table creation
```

More precisely, during a normal round:

```text
pot =
rollover
+ $10 * number_of_agents_entering_this_round
+ fixed_H
```

The design principle is:

```text
X redistributes capital.
Y destroys capital.
H creates capital.

X and Y define the value of risk and intelligence.
H scales the economy to the original table size.
Problem distribution controls jackpot frequency.
```

The dealer should **not use monetary policy to compensate for table size beyond the initial H = 3N scaling**.

That separation is important:

```text
number of agents
    -> H

problem difficulty distribution
    -> rollover frequency

agent intelligence strategy
    -> Y

game outcomes
    -> wealth distribution
```

Keeping those mechanisms separate gives us a much cleaner experiment on whether autonomous agents can learn **when their own intelligence is worth paying for**.
