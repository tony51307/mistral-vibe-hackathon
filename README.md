# mistral-vibe-hackathon

Pay-to-Think dealer economy demo for Mistral Vibe AutoThink.

## What This Demo Shows

Four agents play a 25-round short-answer reasoning game:

- Fast Agent: always buys `none` reasoning.
- Always Think Agent: buys the highest affordable reasoning tier.
- AutoThink Agent: uses an `auto_thinking` adapter to choose a tier from decision agreement and risk.
- Medium Control Agent: buys `medium` when affordable.

The economy follows `economic_model.md`:

- `X`: fixed entry fee, redistributed through the pot.
- `Y`: reasoning spend, burned from the economy.
- `H`: fixed dealer contribution, added to the pot each round.

## Run Locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

The app runs in offline deterministic simulation mode by default.

## Optional Mistral API

Create a local `.env` file:

```env
MISTRAL_API_KEY=...
MISTRAL_CHEAP_MODEL=mistral-small-latest
MISTRAL_STRONG_MODEL=mistral-large-latest
```

Then enable `Use Mistral API` in the Streamlit sidebar.

## AutoThink Boundary

The current `auto_thinking.py` contains a deterministic stub adapter. Replace `StubAutoThinkingAdapter` or add a production adapter later when the real Mistral Vibe AutoThink implementation is ready.
