Pay-to-Think Dealer Economy — V1 Specification
1. Goal
This document defines the V1 economy for the autonomous-agent reasoning game.
The central mechanic is:
Agents have limited capital and must decide how much intelligence is worth buying for each problem.
The dealer controls only the game environment:
problem category;
problem itself;
fixed entry fee;
fixed dealer contribution;
available reasoning-price buckets;
prize distribution.
The dealer does not tell agents whether a problem is easy or hard.
Agents must infer:
how difficult the problem is for themselves;
how capable competitors may be;
whether deeper reasoning is worth its price;
whether conserving bankroll is more valuable.

2. Initial Parameters
Use the following values for V1.
Players:              4
Starting bankroll S:  $80 per agent
Entry fee X:          10DealercontributionH:12 per round

Reasoning prices Y:
  none     $1
  low      $2
  medium   $3
  high     $5
  xhigh    $9

Season length:        25 rounds

Equivalent normalized ratios:
S = 8X
H = 1.2X

For four players:
Normal starting pot:

4 * $10 + $12 = $52

The $ symbol represents game currency, not literal API dollars.

3. Meaning of the Three Monetary Flows
The economy deliberately separates three concepts.
X — Capital at risk
The fixed entry fee is transferred from agents into the prize pot.
X = $10

X is not destroyed.
It moves:
agent bankroll
    ->
prize pot
    ->
winner bankroll

X therefore represents capital at risk.

Y — Cost of intelligence
After seeing the actual problem, each agent selects one reasoning tier.
none     $1
low      $2
medium   $3
high     $5
xhigh    $9

Y is permanently removed from the game economy.
agent bankroll
    ->
reasoning
    ->
burned

Y represents the cost of computation.
The increasing prices are intentionally nonlinear:
1 -> 2 -> 3 -> 5 -> 9

Higher reasoning tiers should require progressively larger expected benefits before becoming economical.

H — External value created by the dealer
The dealer contributes:
H = $12

to every normal round.
H represents the external economic value of successfully solving a task.
Unlike X:
dealer
    ->
prize pot
    ->
winning agents

H introduces new capital into the agent economy.
Unlike Y, it is not linked to actual reasoning expenditure during that round.

4. Economy-Level Balance
Ignoring redistribution through X, the total agent economy changes approximately according to:
change in money supply
=
dealer contribution
-
total reasoning expenditure

For V1:
change per round
=
$12
-
sum of all agents' Y

Example:
Agent A: $1
Agent B: $2
Agent C: $3
Agent D: $5

Total reasoning burn = $11
Dealer injection     = 12Neteconomychange=+1

Another round:
Agent A: $3
Agent B: $5
Agent C: $5
Agent D: $9

Total reasoning burn = $22
Dealer injection     = 12Neteconomychange=-10

The system is therefore allowed to expand or contract from round to round.
The goal is long-run balance, not perfect balance every round.

5. Round Protocol
Phase 1 — Category Reveal
The dealer selects a problem category from a shared taxonomy.
Example:
CATEGORY: PHYSICS

The actual problem is still hidden.
Every active agent commits the fixed entry fee:
X = $10

The dealer adds:
H = $12

With four agents:
Initial pot = $52


Phase 2 — Table Talk
Each agent may publish one message of at most 100 characters.
Example:
"Physics is usually strong for me. Probably willing to spend."

Other agents can observe all messages.
The messages may contain:
claimed category strength;
bluffing;
intimidation;
uncertainty;
comments on past performance;
strategic signals.
Agents cannot communicate again after the problem is revealed.
This creates:
category
+
public signaling
+
historical reputation

before agents know the actual problem.

6. Problem Reveal
The dealer reveals the full problem.
Example:
A particle starts from rest...

All accepted answers should be short and objectively judgeable.
Suitable categories include:
math
physics
computer science
logic
probability
algorithms
general quantitative reasoning

Questions can range from:
1 + 2

to problems requiring substantial reasoning.
The dealer must not expose explicit difficulty metadata.
Agents should never receive fields such as:
difficulty: hard
expected_accuracy: 0.35
recommended_reasoning: high

Difficulty estimation belongs to the agents.

7. Reasoning Purchase
After seeing the problem, every agent independently selects exactly one reasoning tier.
$1  none
$2  low
$3  medium
$5  high
$9  xhigh

The selected Y is immediately deducted from the agent's bankroll.
Example:
Agent bankroll before reasoning: $51

selected:
high = $5

remaining bankroll: $46

The money is burned regardless of whether the final answer is correct.
There are:
no refunds
no partial refunds
no transfers
no loans


8. Reasoning-Level Mapping
The game price should map deterministically to the available Mistral reasoning configuration.
Conceptually:
$1 -> none
$2 -> low
$3 -> medium
$5 -> high
$9 -> xhigh

If the production Mistral endpoint does not provide sufficiently distinct behavior for every named reasoning tier, preserve the game prices and map them internally to available mechanisms.
Possible implementations include:
none:
single inexpensive response

low:
small reasoning budget

medium:
moderate reasoning budget

high:
large reasoning budget

xhigh:
maximum reasoning budget and/or additional verification pass

The game protocol should depend on the abstract reasoning tier rather than a specific API enum.

9. Mandatory Router Pass
Selecting Y itself requires some minimal intelligence.
Therefore every agent receives a small, dealer-funded routing step before purchasing reasoning.
The router can see:
problem
category
current bankroll
current pot
round number
public messages
agent strategy memory
opponent history
available Y buckets

The router should return only a compact decision such as:
{
  "reasoning_tier": "medium"
}

It should not solve the problem.
Its cost is treated as fixed infrastructure cost and does not affect game bankroll.
Therefore:
"none"

means:
no additional paid reasoning beyond the mandatory lightweight routing decision.

10. Answer Submission
After the selected reasoning process finishes, each agent submits one short answer.
Agents cannot:
communicate with competitors;
change Y;
purchase another reasoning tier;
revise an answer after submission.
The dealer determines correctness using a deterministic answer key whenever possible.
Problems should therefore favor short outputs such as:
42
O(n log n)
false
3.2 m/s
B

rather than open-ended essays.

11. Prize Distribution
Let the current total pot be:
P

If exactly one agent answers correctly:
winner receives P

If k agents answer correctly:
each winner receives P / k

Example:
Pot = $52

Correct:
Agent A
Agent C

Each receives:
$26

All agents' reasoning expenditures remain burned.

12. No Correct Answer — Jackpot Rollover
If no agent answers correctly, the entire prize pot rolls into the next round.
Nothing is returned to agents or dealer.
Example:
Round 7 pot: $52

Nobody correct.

Round 8:
rollover          $52
new entry fees    $40
dealer H          $12

new pot          $104

A second unanswered round produces:
$104
+ $40
+ $12
=
$156

This creates naturally varying stakes without revealing problem difficulty.
Higher jackpots should make expensive reasoning economically attractive even when the underlying reasoning-price schedule is unchanged.

13. Jackpot Distribution Policy
For V1, use full rollover:
100% of unresolved pot
->
next round

Do not:
return part to agents
burn the pot
increase H based on difficulty
give the dealer the pot

Suggested safety limit:
maximum rollover chain: 3 unresolved rounds

If needed for demo stability, after a long unresolved chain the dealer may draw the next question from a pool with a reasonable empirical solve rate.
This constraint must remain hidden from agents.
Agents should never receive a difficulty signal.

14. Show Hand
An agent enters Show Hand state when:
0 < bankroll < X

Since:
X = $10

an agent with, for example:
$6

cannot pay the normal entry fee.
It may instead declare:
SHOW HAND

Rules:
entire remaining bankroll enters the pot
agent receives no paid reasoning
agent uses base/no-thinking answer
remaining bankroll becomes $0

If the agent is wrong:
bankroll remains $0
agent is eliminated

If correct:
agent receives its normal share of the pot
agent survives

Show Hand therefore acts as the only comeback mechanism.
There are no:
emergency loans
discounted reasoning
negative balances
bankroll subsidies


15. Bankroll Constraint During Normal Play
An agent may only purchase a reasoning tier it can afford after paying X.
Example:
bankroll before round: $16

after entry:
$6

Available reasoning:
$1 none
$2 low
$3 medium
$5 high

Unavailable:
$9 xhigh

This constraint is important.
As agents become poorer, some forms of intelligence literally become inaccessible.

16. Season Structure
Use fixed-length matches rather than attempting to sustain one economy indefinitely.
V1:
25 rounds per season

At the end:
highest bankroll wins

Then reset:
all agents -> $80
jackpot -> $0

Persistent strategy memory can optionally be:
reset between seasons

or:
preserved between seasons

depending on the experiment.
For initial hackathon demonstrations, reset strategy memory to make runs easier to compare.

17. Problem Distribution
Difficulty should vary widely, but should not be announced.
A useful initial internal distribution is approximately:
trivial/easy     30%
medium           30%
hard             25%
very hard        15%

These labels exist only in the dealer's dataset metadata.
They are never exposed to agents.
The dealer should sample categories independently enough that agents cannot trivially infer difficulty from category.
Avoid mappings such as:
math    -> always hard
logic   -> always easy

Each category should contain a range of difficulty.

18. Category Distribution
Start with approximately balanced categories.
Example:
math                  20%
physics               20%
computer science      20%
logic                  15%
probability            15%
algorithms/reasoning   10%

For a 25-round live season, exact balance is unnecessary.
Across experimental runs, use seeded sampling so different agent policies can be compared on identical problem sequences.

19. Reasoning-Tier Distribution Target
The dealer should not directly enforce how often each Y is selected.
However, the initial economy is calibrated to make a healthy emergent distribution look roughly like:
none       25-35%
low        20-30%
medium     20-30%
high       10-20%
xhigh       2-8%

This is a diagnostic target, not a rule.
Warning signs:
>70% none
-> intelligence probably too expensive

>50% high/xhigh
-> intelligence probably too cheap

almost no medium choices
-> price ladder may not provide useful intermediate tradeoffs


20. Dealer Monetary Policy
For V1:
H = $12

is fixed for every normal round.
It does not depend on:
category
problem difficulty
number of correct agents
previous reasoning expenditure
individual bankroll

This is intentional.
Changing H based on problem difficulty would leak information.
Changing H rapidly based on agent behavior would create exploitable monetary policy.
For experiments with fewer active agents, V1 can either keep:
H = $12

for simplicity, or later migrate to:
H approximately $3 per active seat

For the initial hackathon implementation, keeping H fixed at $12 throughout a 25-round season is simpler and preserves predictable jackpot dynamics.

21. Metrics the Dealer Should Record
Every round should produce a structured event log.
At minimum:
season_id
round_id
problem_id
category
hidden_difficulty
correct_answer

agent_id
bankroll_before
public_message
entry_paid
reasoning_tier
reasoning_cost
bankroll_after_reasoning
submitted_answer
correct
prize_received
bankroll_after_round

pot_before
dealer_contribution
rollover_in
rollover_out
number_correct

Also record actual model telemetry separately:
input tokens
output tokens
reasoning tokens if available
latency
model
API reasoning configuration

Game dollars and real inference usage should remain separate variables.

22. Economy Health Metrics
After every season, compute:
Average reasoning spend
mean Y per active agent per round

Initial target:
approximately $2.5 - $3.2

Reasoning-tier distribution
Check that agents use multiple tiers.
Money supply
Track:
sum of all bankrolls + unresolved jackpot

It should fluctuate rather than collapse immediately or explode continuously.
Show Hand timing
A useful demo range is roughly:
first Show Hand around rounds 15-22

This is not a hard requirement.
Jackpot frequency
Desirable behavior:
single rollover        occasional
double rollover        interesting but uncommon
triple rollover        rare

Reasoning effectiveness
Track:
accuracy by reasoning tier
accuracy by category
accuracy by hidden difficulty
reward per game dollar spent on reasoning


23. Important Non-Features
Do not add these to V1:
variable entry bids
difficulty-dependent H
agent-to-agent transfers
loans
negative bankrolls
wealth-dependent reasoning discounts
confidence wagers
speed bonuses
partial refunds for reasoning
dealer hints about difficulty

These introduce additional strategic variables before we understand the central Pay-to-Think behavior.
V1 should remain:
fixed X
+
fixed H
+
discrete Y
+
private reasoning choice
+
short-answer correctness
+
rollover
+
public pre-question signaling


24. V1 Constants
Implementation-ready defaults:
players: 4

starting_bankroll: 80

entry_fee: 10

dealer_contribution: 12

reasoning_prices:
  none: 1
  low: 2
  medium: 3
  high: 5
  xhigh: 9

season_rounds: 25

message_max_chars: 100

rollover:
  enabled: true
  max_chain_for_demo: 3

show_hand:
  enabled: true
  trigger: "0 < bankroll < entry_fee"
  reasoning_tier: none
  stake: all_remaining_bankroll

The core economic identity to keep in mind during implementation is simply:
X redistributes capital.
Y destroys capital.
H creates capital.

Everything else should emerge from how autonomous agents learn to allocate their limited intelligence.

