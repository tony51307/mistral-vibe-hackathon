# Cat portrait agent

Creates a Mistral **image generation** agent and draws a cat for each table seat.

This is the official Agents + `image_generation` tool flow (same as “Generate an orange cat in an office”).

```bash
# from repo root, with MISTRAL_API_KEY in .env
main_ui/.venv/bin/python -m cat_agent.agent
```

Portraits land in `cat_agent/portraits/{fast,always_think,dynamic}.png`. The Streamlit table uses them as seat avatars.

`--force` regenerates. `--player fast` generates one seat.
