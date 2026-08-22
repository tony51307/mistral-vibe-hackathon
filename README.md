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

The Streamlit game uses a deterministic adapter so it remains reproducible and works
offline. This branch also includes the complete Mistral Vibe CLI with a production
AutoThink router under `vibe/`. AutoThink probes ambiguous requests at low effort,
measures answer stability under controlled perturbations, and escalates only when
the decision is unstable or risky. Trivial prompts use a zero-probe fast path.

Run the integrated CLI and select automatic reasoning:

```bash
uv run vibe
# In Vibe: /thinking auto
```

Run the included routing benchmark and inspect its generated cost, latency, and
routing report:

```bash
uv run python scripts/reasoning_arena.py
```

Evaluation artifacts include:

- `arena-results/report.md`: the original five-task baseline.
- `arena-results-expanded/report.md`: a 20-task Low/High/Auto comparison before
  the latest safety tuning.
- `arena-results-tuned/report.md`: post-tuning AutoThink routing verification.
- `arena-results-adaptive/report.md`: one-model adaptive-probe evaluation.
- `arena-results-value-comparison/analysis.md`: quality/cost comparison of the
  preserved adaptive router and the candidate/critic value router.

Select the value-of-computation strategy without changing models:

```toml
[reasoning_router]
strategy = "value"
```

The default remains `adaptive` for compatibility. The `value` strategy creates
a reusable Low candidate, critiques it for a concrete material defect, and
passes both into the final Low/Medium/High call.

The expanded runner accepts `--repeats N` for repeated trials. The current
single-trial reports expose substantial latency and cost variance, so they should
be treated as development measurements rather than statistically conclusive
benchmarks.
