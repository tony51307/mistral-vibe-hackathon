# mistral-vibe-hackathon

Pay-to-Think poker-table demo for Mistral Vibe Auto Thinking.

[![Mistral Vibe AutoThink live demo](<docs/assets/autothink/Codex Image Aug 22, 2026, 05_19_37 PM.png>)](docs/assets/autothink/Mistral-Vibe-AutoThink-Live-Demo.mp4)

**[▶ Watch the 18-second AutoThink live demo](docs/assets/autothink/Mistral-Vibe-AutoThink-Live-Demo.mp4)**

Captured from the real Mistral Vibe CLI running Mistral Medium 3.5 in `auto` mode.

## Demo

Three agents play a 5-hand math bidding game in the Streamlit UI:

- **The Prodigy**: no-thinker baseline. It still calls the Mistral solver, but Vibe thinking is forced off.
- **The Professor**: always-thinker baseline. It buys high reasoning whenever affordable.
- **The Scientist**: Auto Thinking player. It routes through Vibe CLI with thinking set to `auto`.

Each hand follows the economy in `economic_model.md`:

- `X`: fixed entry fee paid into the pot.
- `Y`: reasoning spend paid for the answer attempt and burned from the economy.
- `H`: fixed dealer contribution added to the pot each hand.

The default dealer agenda is **Repeated Five Step Ladders**. Bluffing is available as a sidebar toggle, but defaults off for the demo.

## Run The UI

Use `uv` for local commands:

```bash
uv run --with streamlit --with PyYAML --with python-dotenv --with mistralai \
  streamlit run main_ui/app.py --server.port 8502 --server.headless true
```

Open:

```text
http://localhost:8502
```

The main control is **Auto-play 5 hands**. The UI starts at `0 / 5`, then advances through each hand while showing the latest result in the middle of the table.

## Live Mistral And Vibe CLI

Create a local `.env` file and do not commit it:

```env
MISTRAL_API_KEY=...
MISTRAL_CHEAP_MODEL=mistral-small-latest
MISTRAL_STRONG_MODEL=mistral-small-latest
```

The Streamlit sidebar includes:

- **Live Mistral API**: enables live solver calls; otherwise the demo falls back to deterministic seeded play.
- **Solver backend**: defaults to `Vibe CLI`; `Direct SDK` is kept as a fallback.
- **Enable bluffing**: enables sequential 50-word table talk before bid decisions.

With the Vibe CLI backend, the no-thinker, always-thinker, and Auto Thinking agent all call the same answer path with different thinking settings.

## Cache Prewarm

The UI caches live solver responses for the first 5 hands in:

```text
main_ui/.cache/live_solver_first5.json
```

Prewarm the active cache with:

```bash
uv run python main_ui/prewarm_cache.py --rounds 5
```

This makes live Vibe/Mistral calls and can take several minutes. The demo intentionally adds one second of solver latency per live call so autoplay feels closer to a real API-backed table.

## Auto Thinking Notes

The Auto Thinking design is summarized in `mistral_vibe_auto_thinking.md`. In this demo, Auto Thinking is represented by the Scientist agent and routed through the Vibe CLI wrapper in `main_ui/vibe_client.py`.

To use Vibe directly:

```bash
uv run vibe
# In Vibe: run /thinking, then select auto
```

Each routed turn displays a live AutoThink card that advances through task
analysis, low-cost probing, verification when needed, and final gear selection.
The card shows routing stability and a compact decision path without exposing
private chain-of-thought. After a turn, inspect the latest route or the session
dashboard:

```text
/thinking explain
/thinking stats
```

A reliable high-gear demo prompt is:

```text
What is the probability of exactly three heads in ten fair coin flips? Answer only with the final fraction.
```
<<<<<<< HEAD
=======

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
>>>>>>> codex/autothink-arena-hackathon
