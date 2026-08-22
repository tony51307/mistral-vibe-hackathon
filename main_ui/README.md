# Pay-to-Think Dealer Table

Four agents compete under the canonical V1 dealer economy from `dealer/`.
Each agent pays the same entry fee `X`, buys exactly one private reasoning tier
`Y`, and tries to win the dealer-funded pot.

## Idea

- **Fast** selects `none`.
- **Always Think** prefers `high` / `xhigh`.
- **Dynamic** uses an AutoThink-style routing policy.
- **Control** uses a balanced low/medium policy.

The dealer owns the agenda, hidden difficulty, answer keys, deterministic
judging, payout, and audit event. The public table sees only category, prompt,
pot, messages, selected reasoning tier, and final outcome.

## Setup

```bash
cd mistral_hackathon
python3 -m venv .venv
source .venv/bin/activate
pip install -r main_ui/requirements.txt
streamlit run main_ui/app.py
```

Seeded mode currently uses deterministic offline solvers against the canonical
dealer problem bank.

## Costs

| Tier | Credits |
| --- | --- |
| none | 1 |
| low | 2 |
| medium | 3 |
| high | 5 |
| xhigh | 9 |

Entry fees go into the prize pool. Reasoning purchases are burned.
