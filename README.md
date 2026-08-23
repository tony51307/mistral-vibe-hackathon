# mistral-vibe-hackathon

Pay-to-Think poker-table demo for Mistral Vibe Auto Thinking.

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
# In Vibe: /thinking auto
```
