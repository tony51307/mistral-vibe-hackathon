# Configuring a dealer table

`table_modes_v1.yaml` is the machine-readable setup for the supported 2-to-8-agent tables. `table_size.md` is the full economic rationale and remains the design authority.

The V1 constants stay fixed at `$80` starting bankroll, `$10` entry, and the existing reasoning-price ladder. Only the dealer contribution is derived when the season is created:

```text
fixed H for the season = $3 * initial number of agents
```

Eliminations do not reduce `H` later in the season.

## Choose a preset

| Mode | Initial agents | Fixed H | Normal opening pot | Suggested agenda |
| --- | ---: | ---: | ---: | ---: |
| `heads_up` | 2 | $6 | $26 | 1, balanced ramp |
| `baseline` | 4 | $12 | $52 | 5, seeded benchmark |
| `demo` | 6 | $18 | $78 | 3, jackpot pressure |
| `tournament` | 8 | $24 | $104 | 3, jackpot pressure |

Validate a mode with the dealer CLI:

```bash
.venv/bin/python -m game.dealer_distributor \
  --bank data/pay_to_think_problem_bank_v1.json \
  --agendas data/pay_to_think_agendas_v1.yaml \
  --tables tables/table_modes_v1.yaml \
  --table demo \
  --strategy 3 \
  --seed 260822 \
  --validate-only
```

The selected strategy can differ from the recommendation when an experiment requires the same agenda across table sizes. Keep it explicit and hold it constant for comparisons.

## Build a game from a preset

```python
from game import DealerGame, load_agendas, load_problem_bank, load_table_modes

bank = load_problem_bank("data/pay_to_think_problem_bank_v1.json")
agendas = load_agendas("data/pay_to_think_agendas_v1.yaml", bank)
tables = load_table_modes("tables/table_modes_v1.yaml", agendas)

game = DealerGame.from_table_mode(
    table_catalog=tables,
    mode_id="demo",
    problem_bank=bank,
    agenda_catalog=agendas,
    seed=260822,
)
```

Default IDs are `agent_1` through `agent_N`. To bind real policy names, pass exactly `N` unique IDs:

```python
game = DealerGame.from_table_mode(
    table_catalog=tables,
    mode_id="baseline",
    player_ids=["fast", "always_think", "dynamic", "control"],
    problem_bank=bank,
    agenda_catalog=agendas,
    seed=260822,
)
```

## Add a custom table mode

Copy one item in `table_modes_v1.yaml`, give it a unique `id`, and set `initial_agent_count` between 2 and 8. Choose an existing agenda strategy from 1 through 5 and document at least one use case.

Do not add an `H` override to a mode. The loader rejects changes to the frozen economy contract, and the dealer derives `H` from the initial count exactly once.
