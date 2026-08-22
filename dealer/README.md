# Pay-to-Think dealer core

This directory contains the deterministic V1 dealer boundary for the hackathon game. It loads the canonical problem bank, follows one fixed 25-round agenda, enforces the game economy and phase order, judges short answers without an LLM, and writes one reproducible JSONL record per completed round.

Provider calls are intentionally not implemented here. Routers and solvers are injected into `DealerGame`, so a Mistral adapter can be added without giving model-facing code access to answer keys or dealer metadata.

## Layout

```text
game/
  dealer_distributor.py  phase-checked round and season orchestration
  economy.py             affordability and exact-cent pot splitting
  event_log.py           append-only JSONL output
  judge.py               deterministic answer validators
  loaders.py             bank/agenda schema and cross-file validation
  models.py              typed state and configuration
  reasoning_provider.py  abstract router/solver adapter boundary
  rotation.py            fixed-agenda problem cursor
data/                     canonical V1 bank and five agendas
docs/                     source implementation guide
agents/                   LLM/deterministic profiles and 6–10-seat rosters
tables/                   2-to-10-agent economy instructions and presets
tests/                    judge, economy, loader, and visibility tests
```

## Set up and verify

Use a project-local environment:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m unittest discover -s tests -v
```

Validate the canonical files and select an agenda without starting provider calls:

```bash
.venv/bin/python -m game.dealer_distributor \
  --bank data/pay_to_think_problem_bank_v1.json \
  --agendas data/pay_to_think_agendas_v1.yaml \
  --tables tables/table_modes_v1.yaml \
  --table baseline \
  --strategy 3 \
  --seed 260822 \
  --validate-only
```

## Embedding the dealer

The host application advances the state machine explicitly:

```python
from game import DealerGame, load_agendas, load_problem_bank, load_table_modes

bank = load_problem_bank("data/pay_to_think_problem_bank_v1.json")
agendas = load_agendas("data/pay_to_think_agendas_v1.yaml", bank)
tables = load_table_modes("tables/table_modes_v1.yaml", agendas)
game = DealerGame.from_table_mode(
    table_catalog=tables,
    mode_id="baseline",
    player_ids=["fast", "always_think", "dynamic", "control"],
    problem_bank=bank,
    agenda_catalog=agendas,
    strategy_number=3,
    seed=260822,
    output_path="runs/strategy_3_run_001.jsonl",
)

category_payloads = game.reveal_category()
game.collect_entries()
game.record_table_talk({agent_id: "" for agent_id in category_payloads})
problem_payloads = game.reveal_problem()
game.route_and_purchase(routers)
game.solve(solvers)
results = game.judge()
prizes = game.payout()
event = game.complete_round()
```

Each router is called with a public payload and returns `{"reasoning_tier": "medium"}`. Each solver returns `{"answer": "1/2"}` and may add token, latency, model, and API-reasoning telemetry fields. The judge ignores every solver field except `answer` for correctness.

See [tables/README.md](tables/README.md) for the heads-up, baseline, demo, and tournament configurations. Table modes derive a fixed season contribution of `$3 × initial agents`; the direct `player_ids` constructor remains available for isolated tests and custom hosts.

See [agents/README.md](agents/README.md) for LLM profile loading, environment-only Mistral configuration, bluff/listening policies, and the `social_6` through `social_10` rosters.

## Invariants

- The problem bank is authoritative. Agenda category, difficulty, and guessability must match it exactly.
- Category reveal omits problem identity; problem reveal is built from a three-field public whitelist.
- The five hidden metadata/answer fields are covered by recursive visibility tests.
- Entry and pot amounts use integer cents. Reasoning spend is burned, never added to the pot.
- Supported table modes use 2–10 initial agents and freeze `H = $3 × N0` for the season.
- Split remainders roll forward instead of being assigned randomly.
- Show Hand stakes the remaining bankroll and forces a zero-cost base answer.
- A V1 edge case exists when bankroll equals the entry fee exactly: the player can legally enter but cannot afford the priced `none` tier. The core forces a zero-cost base answer and logs `router_fallback=true`, preserving both the frozen entry rule and the no-negative-bankroll invariant.
- Agenda names, objectives, hidden metadata, canonical answers, and future rounds remain dealer-only.

The JSONL audit record contains hidden fields for offline analysis. It must not be reused as an agent prompt.
