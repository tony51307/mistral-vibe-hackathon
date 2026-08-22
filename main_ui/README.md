# Pay-to-Think Math Bidding

Three Mistral-powered agents compete in a math bidding game. Each one spends
**thinking credits** and must decide whether deeper reasoning is worth the pot.

## Idea

- **Fast** never thinks (1 credit).
- **Always Think** always buys deep reasoning (8 credits).
- **Dynamic** runs a cheap first pass plus 3–5 perturbation probes, then pays
  for deep reasoning only when answers disagree or confidence is low and the
  prize is high.

**Phase 1** is a sealed entrance: the same fixed fee for every agent, ENTER or
DECLINE. Fees are added to the pot. There is no bidding or raising.

**Phase 2** is private calculation in cycles. Agents publicly THINK(amount),
PASS, or EXIT. They can see credit purchases, not answers or traces. If a
cycle has no correct answer, the dealer says so without revealing wrong
answers. Only the winning cycle is paid. Multiple winners split equally. If
nobody wins, the whole pot rolls over.

## Setup

```bash
cd mistral_hackathon
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add MISTRAL_API_KEY if you want live models
streamlit run app.py
```

Environment:

```
MISTRAL_API_KEY=...
MISTRAL_CHEAP_MODEL=mistral-medium-3-5
MISTRAL_STRONG_MODEL=mistral-medium-3-5
```

Seeded mode (default, no API key) uses curated stubs so Dynamic visibly
revises traps such as `1/6 → 5/33` on the red-ball probability problem.

## Costs

| Call | Credits |
| --- | --- |
| Cheap | 1 |
| Perturbation | 1 each |
| Deep | 8 |

Entrance fees go into the prize pool. THINK purchases buy reasoning only.
