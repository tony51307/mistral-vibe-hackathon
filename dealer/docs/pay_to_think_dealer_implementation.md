# Pay-to-Think Dealer Distributor & Judge — Implementation Guide

## 1. Inputs

The baseline uses two data files:

- `pay_to_think_problem_bank_v1.json` — canonical problem bank and validators.
- `pay_to_think_agendas_v1.yaml` — ordered 25-round agendas.

Mixed-bank strategies 11–15 additionally use:

- `pay_to_think_reasoning_sensitive_additions_v2.json` — 42 reasoning-sensitive problems.
- `pay_to_think_mixed_old_new_agendas_v3.yaml` — mixed V1/V2 problem rotations.

Each problem bank is authoritative for its prompts, answers, and dealer metadata. An agenda contains only selection/order metadata and must never override a source problem.

Recommended V1 economy constants:

```yaml
starting_bankroll: 80
entry_fee_X: 10
dealer_contribution_H: 12
reasoning_prices_Y:
  none: 1
  low: 2
  medium: 3
  high: 5
  xhigh: 9
season_rounds: 25
message_max_chars: 100
```

## 2. Suggested scripts

Implement two small Python programs/modules:

```text
dealer_distributor.py
judge.py
```

Keep game-state accounting in the distributor. Keep answer parsing/correctness in the judge.

A third optional file, `models.py`, can hold typed dataclasses/Pydantic models shared by both.

---

# 3. `dealer_distributor.py`

## Responsibilities

The distributor should:

1. Load the problem bank.
2. Load one agenda by `strategy_number`.
3. Maintain round, bankroll, pot, rollover, and active-player state.
4. Reveal only the category before entry/table talk.
5. Collect the fixed entry fee `X`.
6. Add fixed dealer contribution `H`.
7. Collect one public message per agent, maximum 100 characters.
8. Reveal the problem text.
9. Ask each eligible agent's router to choose one `Y` tier.
10. Enforce affordability.
11. Deduct `Y` as burned compute currency.
12. Run the selected solver configuration.
13. Send submitted answers to `judge.py`.
14. Distribute the pot or roll it over.
15. Apply Show Hand rules.
16. Write a complete event log.

## CLI shape

Example:

```bash
python dealer_distributor.py \
  --bank pay_to_think_problem_bank_v1.json \
  --agendas pay_to_think_agendas_v1.yaml \
  --strategy 3 \
  --seed 260822 \
  --output runs/strategy_3_run_001.jsonl
```

`--strategy` is the agenda's `strategy_number`, not a model's private strategy.

## Round state machine

Use an explicit phase enum:

```text
CATEGORY_REVEAL
ENTRY
TABLE_TALK
PROBLEM_REVEAL
ROUTING
SOLVING
JUDGING
PAYOUT
ROUND_COMPLETE
```

Do not let agent calls skip or reorder phases.

## Category reveal

Before the entry/table-talk phase, give agents only:

```json
{
  "round": 7,
  "season_rounds": 25,
  "category": "probability",
  "bankroll": 43,
  "entry_fee": 10,
  "current_rollover": 52
}
```

Do not expose:

```text
dealer_difficulty
guessability
correct answer
suggested reasoning tier
future agenda order
```

## Entry and pot accounting

For each normal active agent:

```text
bankroll -= X
pot += X
```

Then exactly once per round:

```text
pot += H
```

`H` is fixed at `$12` in V1. Do not change it by category or hidden difficulty.

If there is rollover:

```text
pot = rollover_in + collected_entry_fees + H
```

## Table talk

Allow one UTF-8 message per agent with a maximum of 100 characters.

Store both the original and a sanitized display form. Do not use table-talk text to judge correctness.

All active agents receive all table-talk messages before the actual problem is revealed.

## Problem reveal

Retrieve `prompt_markdown` from the canonical JSON bank using the agenda's `problem_id`.

Agent payload:

```json
{
  "problem_id": "prob_007",
  "category": "probability",
  "prompt_markdown": "...",
  "pot": 52,
  "bankroll_after_entry": 33,
  "round": 7,
  "season_rounds": 25,
  "reasoning_menu": {
    "none": 1,
    "low": 2,
    "medium": 3,
    "high": 5,
    "xhigh": 9
  }
}
```

## Router contract

Use a small structured-output call. The router does not receive the answer key.

Required output:

```json
{
  "reasoning_tier": "medium"
}
```

Optionally log a private short reason for research, but do not require it for gameplay.

Validate the tier against:

```text
none | low | medium | high | xhigh
```

## Affordability

After entry, an agent may select only a tier whose price is less than or equal to its bankroll.

If an invalid/unaffordable tier is returned:

1. Retry router once with the affordable tier list.
2. If still invalid, fall back to the highest affordable tier only if the model explicitly tried to overspend; otherwise fall back to `none`.
3. Log `router_fallback=true`.

Never permit a negative bankroll.

## Solver contract

Map game tiers to the currently supported Mistral reasoning configuration in one central mapping function:

```python
def reasoning_config(tier: str) -> dict:
    ...
```

Do not scatter provider-specific values through the game code.

Every solver must return:

```json
{
  "answer": "1/2"
}
```

For game correctness, ignore prose outside the structured `answer` field.

Store real token counts and latency separately from game-dollar cost.

## Show Hand

Trigger when:

```text
0 < bankroll < X
```

before normal entry.

Behavior:

```text
stake = all remaining bankroll
bankroll = 0
pot += stake
reasoning tier = none
reasoning cost = 0 additional game dollars
```

The agent still receives the problem and submits a base/no-thinking answer.

If correct, normal prize distribution can revive it. If wrong, it remains at zero and becomes inactive.

A player with bankroll exactly zero cannot enter.

---

# 4. `judge.py`

## Design principle

Do not use an LLM judge for V1.

The bank was intentionally designed around deterministic validators.

Expose one main function:

```python
def judge_answer(problem: dict, submitted: str) -> JudgeResult:
    ...
```

Suggested result:

```json
{
  "correct": true,
  "parsed_value": 0.5,
  "validator_kind": "numeric",
  "error": null
}
```

## Validator kinds

### `integer`

- Strip surrounding whitespace.
- Optionally remove outer math delimiters.
- Parse a signed base-10 integer.
- Require exact equality.

Reject explanatory text unless a safe answer extractor is explicitly implemented.

### `numeric`

Accept:

```text
0.5
1/2
-3
3.14159
```

Procedure:

1. Normalize Unicode and whitespace.
2. Remove simple surrounding `$...$`, `\(...\)`, or `\[...\]`.
3. Try integer/float parsing.
4. If that fails, parse a simple signed fraction `a/b`.
5. Reject division by zero.
6. Compare with the canonical numeric value using `abs_tolerance`.

Do not execute arbitrary expressions with `eval`.

### `boolean`

Normalize case and whitespace.

Accept only the configured aliases, e.g.:

```text
true / yes
false / no
```

### `normalized_text`

Apply only the normalization operations declared in the problem:

```text
trim
unicode_nfkc
casefold
remove_math_delimiters
collapse_whitespace
```

Then compare against the canonical `accepted` list.

For complexity answers, normalization may additionally standardize spaces, but avoid symbolic algebra equivalence in V1.

## Parse failures

A parse failure is simply incorrect:

```json
{
  "correct": false,
  "parsed_value": null,
  "error": "parse_failure"
}
```

Never ask the model to clarify after seeing the problem; that would create an extra reasoning opportunity.

---

# 5. Prize distribution

After all answers have been judged:

```text
winners = all correct agents
```

If there is one winner:

```text
winner bankroll += pot
rollover_out = 0
```

If there are multiple winners:

```text
share = pot / number_of_winners
```

Use exact integer game dollars if possible. Since V1 values can create non-integer splits, choose one policy and keep it deterministic.

Recommended implementation:

```text
represent all game currency internally as integer cents
```

For example `$10` is `1000` cents. Divide the pot in cents.

If division leaves a remainder, carry the remainder into the next round's rollover instead of assigning it randomly.

If nobody is correct:

```text
rollover_out = pot
```

Do not burn or refund the pot.

---

# 6. Agenda strategies

The two YAML catalogs contain fifteen fixed strategies:

1. `balanced_ramp` — gradual increase in difficulty with mixed categories.
2. `bait_and_switch` — alternates easy and hard questions so category alone is not enough.
3. `jackpot_pressure` — clusters hard questions to encourage rollover and pot-sensitive reasoning.
4. `category_specialization` — category blocks to expose specialization and reputation effects.
5. `seeded_mixed_benchmark` — reproducible mixed test for A/B comparisons.
6. `adaptive_sawtooth` — alternates cheap captures and hard reasoning payoffs.
7. `budget_then_battle` — rewards saving capital for a difficult late block.
8. `guessability_traps` — separates answer priors from actual reasoning need.
9. `reasoning_tier_ladder` — emphasizes low/medium decision boundaries.
10. `repeated_five_step_ladders` — repeats difficulty ladders across categories.
11. `dynamic_margin_interleave` — interleaves cheap legacy and reasoning-sensitive rounds.
12. `middle_tier_harvest` — concentrates useful low/medium reasoning purchases.
13. `anti_shallow_trap` — emphasizes tempting but incorrect shallow answers.
14. `bankroll_preserve_then_convert` — saves capital before a reasoning-heavy late block.
15. `five_wave_dynamic_test` — repeats mixed-bank reasoning waves across categories.

For scientific comparisons, use the same agenda and model seeds across policies whenever possible.

Strategies 6–15 are intentionally showcase-biased. Pair them with seeded mixed
or randomized agendas before making comparative or scientific claims.

Do not reveal strategy number/name/objective to agents.

---

# 7. Event log

Write one JSONL record per round.

Minimum round-level fields:

```json
{
  "season_id": "s001",
  "round": 1,
  "strategy_number": 3,
  "problem_id": "cs_009",
  "category": "computer_science",
  "rollover_in": 0,
  "entry_total": 40,
  "dealer_H": 12,
  "pot": 52,
  "winner_ids": ["agent_b"],
  "rollover_out": 0
}
```

Include an `agents` array with, for each agent:

```text
bankroll_before
entry_paid
show_hand
public_message
bankroll_after_entry
router_tier
reasoning_price
actual_input_tokens
actual_output_tokens
actual_reasoning_tokens if available
latency_ms
submitted_answer
correct
prize_received
bankroll_after_round
router_fallback
```

Also log dealer-only metadata such as hidden difficulty for offline analysis, but keep it out of every agent prompt.

---

# 8. Determinism and reproducibility

Accept a run seed.

Use it for:

- any randomized agenda selection;
- randomized player order;
- model sampling seeds when the provider supports them.

Record:

```text
problem-bank hash
agenda-file hash
model identifier
reasoning-tier mapping version
run seed
code version / git commit
```

This is especially important when comparing Always-Fast, Always-High, and Pay-to-Think policies.

---

# 9. Unit tests

At minimum test:

### Judge

```text
"1/2" == 0.5
"0.5" == 0.5
" YES " == true
"LIFO" == "lifo"
malformed fraction -> incorrect
"1/0" -> incorrect
arbitrary Python expression -> never executed
```

### Economy

```text
entry fees enter pot
H added once
Y is burned
winners split pot correctly
unresolved pot rolls over
no negative bankroll
Show Hand uses all remaining capital
remainder cents carry into rollover
```

### Information isolation

Assert that an agent payload never contains:

```text
answer
validator
dealer_meta
difficulty
guessability
suggested_reasoning_tier
future rounds
```

This should be a test, not just a convention.

---

# 10. Recommended code boundary

A clean V1 layout:

```text
game/
  dealer_distributor.py
  judge.py
  models.py
  reasoning_provider.py
  economy.py
  event_log.py

data/
  pay_to_think_problem_bank_v1.json
  pay_to_think_agendas_v1.yaml

tests/
  test_judge.py
  test_economy.py
  test_visibility.py
```

Keep the Mistral API adapter inside `reasoning_provider.py`. The game engine should only understand abstract tiers such as `none`, `low`, `medium`, `high`, and `xhigh`.

That allows the same dealer to later compare different models or reasoning implementations without changing the economic rules.
