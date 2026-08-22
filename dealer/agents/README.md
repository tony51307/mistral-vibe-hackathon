# Agent profiles and 6–10-seat rosters

`agent_rosters_v1.yaml` translates the agent-archetype and bluffing notes into validated runtime configuration. It defines ten reusable profiles and five cumulative rosters: `social_6` through `social_10`.

The social design keeps four policies independent:

```text
speech + listening/belief + reasoning purchase + answering
```

Table talk remains category-only, simultaneous, one message per agent, and at most 100 characters. Communication closes when the full problem is revealed. Public history never contains an answer key, hidden difficulty, chain of thought, confidence trace, or private strategy memory.

## Included profiles

| Profile | Runtime | Reasoning policy | Bluff mode | Listens |
| --- | --- | --- | --- | --- |
| `prodigy` | LLM | always none | none | yes |
| `professor` | LLM | always high | none | no |
| `scientist` | LLM | perturbation router | none | no |
| `quant` | LLM | bankroll/pot value | honest | yes |
| `bluffer` | LLM | dynamic | strategic | yes |
| `honest_signaler` | LLM | dynamic | honest | yes |
| `shark` | LLM | opponent-aware | strategic | yes |
| `monk` | deterministic | always none | none | no |
| `degenerate` | deterministic | always none | none | no |
| `darwin` | LLM | learned | learned | yes |

The Scientist is the required social-blind dynamic baseline: it receives the same game state, but its host adapter should remove table talk according to `listen_to_table_talk: false`.

Apply that boundary before calling an agent:

```python
from game import prepare_agent_context

profile = agents.profile_for_agent("social_6", "scientist")
agent_payload = prepare_agent_context(problem_payloads["scientist"], profile)
```

Validate a complete roster without making provider calls:

```bash
.venv/bin/python -m game.dealer_distributor \
  --bank data/pay_to_think_problem_bank_v1.json \
  --agendas data/pay_to_think_agendas_v1.yaml \
  --agents agents/agent_rosters_v1.yaml \
  --roster social_10 \
  --strategy 3 \
  --seed 260822 \
  --validate-only
```

## Load a roster into the dealer

```python
from game import DealerGame, load_agent_catalog, load_agendas, load_problem_bank

bank = load_problem_bank("data/pay_to_think_problem_bank_v1.json")
agendas = load_agendas("data/pay_to_think_agendas_v1.yaml", bank)
agents = load_agent_catalog("agents/agent_rosters_v1.yaml")

game = DealerGame.from_agent_roster(
    agent_catalog=agents,
    roster_id="social_10",
    problem_bank=bank,
    agenda_catalog=agendas,
    seed=260822,
)
```

The roster fixes player IDs, profile bindings, the initial seat count, and a recommended agenda. The dealer derives the season-wide contribution as `$3 × initial agents`, so `social_6` uses `$18` and `social_10` uses `$30`. The value remains fixed after eliminations.

The host may override a roster recommendation with any registered positive
strategy number. Strategies 6–10 exercise the dynamic-edge showcase agendas;
for example, pass `strategy_number=9` to compare the agents on the reasoning
tier ladder. Strategies 11–15 require both problem banks and both agenda
catalogs to be loaded with `load_problem_banks` and `load_agenda_catalogs`.

## Resolve an LLM profile

Credentials remain environment-only. The checked-in defaults refer to:

```text
MISTRAL_MODEL
MISTRAL_API_KEY
```

The loader never returns or logs the API key:

```python
from game import load_agent_catalog, resolve_llm_runtime

catalog = load_agent_catalog("agents/agent_rosters_v1.yaml")
profile = catalog.get_profile("scientist")
runtime = resolve_llm_runtime(profile)

print(runtime.provider)
print(runtime.model_id)
print(runtime.api_key_env)  # variable name only, never its value
```

`resolve_llm_runtime` validates that the model identifier and credential variables exist. It leaves the actual provider call to the host adapter. No provider model ID is invented or committed.

## Add or change a profile

Each profile must declare:

- a unique ID, display name, archetype, and runtime;
- separate speech, listening, reasoning, and answering policies;
- a bluff mode and whether table talk is heard;
- an LLM persona for `runtime: llm`, or a deterministic answer policy otherwise.

Each roster must contain 6–10 consecutive seats, unique agent IDs, and only declared profile IDs. Copy a roster, change its ID and seats, then run:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

The full source notes are preserved under `agents/docs/`.
