"""Pay-to-Think math bidding demo — Streamlit poker-table UI."""

from __future__ import annotations

import base64
import html
from pathlib import Path
import sys
import time

import streamlit as st

UI_ROOT = Path(__file__).resolve().parent
if sys.path[:1] != [str(UI_ROOT)]:
    sys.path.insert(0, str(UI_ROOT))

from game import GameConfig, GameState, agenda_labels, new_game, play_round, roster_labels

if sys.path[:1] != [str(UI_ROOT)]:
    sys.path.insert(0, str(UI_ROOT))

from mistral_client import MistralClient
from vibe_client import VibeCliClient


st.set_page_config(page_title="Pay-to-Think Table", layout="wide")

PORTRAIT_ROOT = UI_ROOT.parent / "cat_agent" / "portraits"

SEAT_EMOJI = {
    "The Prodigy": "⚡",
    "The Professor": "🧠",
    "The Scientist": "🎯",
    "The Quant": "📈",
    "The Bluffer": "🎭",
    "The Honest Signaler": "⚖️",
    "The Shark": "♠",
    "The Monk": "◯",
    "The Degenerate": "🎲",
    "Darwin": "🧬",
}

PITCH = """
Canonical V1 dealer economy: fixed entry fee X, dealer contribution H,
and one private reasoning purchase Y. Difficulty and answer keys stay dealer-only.
The **side rail** is the dealer’s audit view.
"""

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Libre+Baskerville:wght@700&family=IBM+Plex+Sans:wght@400;600;700&display=swap');
.block-container { padding-top: 1rem; max-width: 1400px; }

.room {
  position: relative;
  height: 720px;
  background:
    radial-gradient(circle at 50% 45%, #3a2818 0%, #1a100a 75%);
  border-radius: 18px;
  overflow: visible;
  font-family: 'IBM Plex Sans', sans-serif;
  color: #f4efe4;
}
.dealer-cat {
  position: absolute;
  left: 50%;
  top: 15%;
  transform: translateX(-50%);
  z-index: 5;
  text-align: center;
}
.dealer-cat img, .dealer-cat .seat-avatar {
  width: 118px;
  height: 118px;
  border-radius: 50%;
  object-fit: cover;
  object-position: 50% 18%;
  border: 3px solid #f5d76e;
  box-shadow: 0 8px 18px rgba(0,0,0,.45);
}
.dealer-cat .label {
  margin-top: 4px;
  font-size: 11px;
  letter-spacing: .16em;
  text-transform: uppercase;
  color: #f5d76e;
  font-weight: 800;
}
.table {
  position: absolute;
  left: 50%;
  top: 55%;
  width: min(420px, 64%);
  height: min(400px, 66%);
  transform: translate(-50%, -50%);
  border-radius: 50%;
  background:
    radial-gradient(circle at 50% 42%, #2a8a4a 0%, #145c2e 55%, #0a3318 100%);
  border: 14px solid #6b3e14;
  box-shadow:
    inset 0 0 0 6px #d4af37,
    inset 0 0 70px rgba(0,0,0,.35),
    0 18px 40px rgba(0,0,0,.45);
}
.table-center {
  position: absolute;
  left: 50%;
  top: 38%;
  transform: translate(-50%, -50%);
  width: 68%;
  text-align: center;
}
.felt-top {
  letter-spacing: .16em;
  font-size: 11px;
  color: #d8c27a;
  text-transform: uppercase;
  margin-bottom: 8px;
}
.pot-chip {
  display: inline-block;
  background: #111;
  color: #f5d76e;
  border: 2px dashed #f5d76e;
  border-radius: 999px;
  padding: 5px 14px;
  font-weight: 700;
  font-size: 17px;
}
.problem-card {
  margin: 10px auto 0;
  background: #fffaf0;
  color: #1a1208;
  border-radius: 8px;
  padding: 10px 12px;
  font-family: 'Libre Baskerville', serif;
  font-size: 15px;
  line-height: 1.4;
  max-height: 160px;
  overflow: auto;
}
.problem-meta {
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 10px;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: #7a5c20;
  margin-bottom: 4px;
}
.seat {
  position: absolute;
  width: 174px;
  background: #140e0a;
  border: 2px solid #c9a227;
  border-radius: 16px;
  padding: 9px 11px;
  z-index: 3;
  box-shadow: 0 8px 18px rgba(0,0,0,.4);
}
.seat.winner { box-shadow: 0 0 0 3px #f5d76e, 0 8px 18px rgba(0,0,0,.4); }
.seat.folded { opacity: .5; }
.seat-pos {
  left: var(--seat-x);
  top: var(--seat-y);
  transform: translate(-50%, -50%);
}
.seat-head {
  display: grid;
  grid-template-columns: 56px 1fr;
  gap: 8px;
  align-items: center;
}
.seat-avatar {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  object-fit: cover;
  object-position: 50% 18%;
  border: 1px solid #f5d76e;
}
.seat-name { font-weight: 700; font-size: 14px; line-height: 1.15; }
.seat-role {
  margin-top: 4px;
  color: #f5d76e;
  font-size: 11px;
  font-weight: 800;
}
.seat-stack { color: #b7e4c7; font-size: 13px; font-weight: 700; margin: 6px 0 4px; }
.seat-action {
  display: inline-block;
  background: #c9a227;
  color: #1a1208;
  font-weight: 700;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
}
.seat-ans {
  margin-top: 8px;
  font-family: 'Libre Baskerville', serif;
  font-size: 15px;
  line-height: 1.35;
}
.seat-ans .mark { font-family: 'IBM Plex Sans', sans-serif; font-weight: 800; }
.seat-ans .mark.ok { color: #7dcea0; }
.seat-ans .mark.no { color: #f5a3a3; }
.seat-think { font-size: 12px; color: #ddd; margin-top: 4px; }
.dealer-answer {
  margin-top: 10px;
  display: inline-block;
  font-size: 13px;
  line-height: 1.3;
  color: #050505;
  background: #ffe08a;
  font-weight: 900;
  padding: 4px 8px;
  border-radius: 4px;
}
.rail {
  background: #1b140c;
  border: 1px solid #6b4f1d;
  border-radius: 10px;
  padding: 8px 10px;
  color: #f4efe4;
  min-height: 0;
}
.rail h3 {
  margin: 0 0 6px;
  font-size: 17px;
  letter-spacing: .12em;
  text-transform: uppercase;
  color: #f5d76e;
}
.hole { background: #2a2116; border-radius: 8px; padding: 6px 8px; margin-bottom: 6px; }
.hole .who { font-weight: 700; font-size: 11px; color: #f5d76e; }
.hole .ans { font-family: 'Libre Baskerville', serif; font-size: 15px; margin: 2px 0; }
.hole .tag { font-size: 10px; color: #c9c0a8; }
.tag.ok { color: #7dcea0; }
.tag.no { color: #f5a3a3; }
.below-table {
  margin-top: 72px;
}
.talk-log {
  background: #18130f;
  border: 1px solid #6b4f1d;
  border-radius: 10px;
  padding: 10px 12px;
  color: #f4efe4;
}
.talk-log h3 {
  margin: 0 0 8px;
  font-size: 14px;
  letter-spacing: .12em;
  text-transform: uppercase;
  color: #f5d76e;
}
.talk-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
  gap: 8px;
}
.talk-item {
  background: #251c13;
  border-radius: 8px;
  padding: 8px 10px;
  min-height: 68px;
}
.talk-who {
  font-size: 11px;
  font-weight: 800;
  color: #f5d76e;
  margin-bottom: 4px;
}
.talk-msg {
  font-size: 12px;
  line-height: 1.35;
  color: #f4efe4;
}
</style>
"""


def init_state(config: GameConfig) -> None:
    st.session_state.game = new_game(config)
    st.session_state.client = MistralClient()
    st.session_state.vibe_client = VibeCliClient()
    st.session_state.last = None
    st.session_state.round_error = None
    st.session_state.autoplay = False


def current_game() -> GameState:
    return st.session_state.game


def run_one() -> None:
    try:
        game = current_game()
        solver_backend = getattr(game.config, "solver_backend", "vibe_cli")
        client = (
            st.session_state.vibe_client
            if solver_backend == "vibe_cli"
            else st.session_state.client
        )
        st.session_state.last = play_round(game, client)
        st.session_state.round_error = None
    except Exception as exc:
        st.session_state.round_error = str(exc)
        st.session_state.last = st.session_state.get("last")


def main() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    if "game" not in st.session_state:
        init_state(GameConfig())
    if "autoplay" not in st.session_state:
        st.session_state.autoplay = False

    st.title("Pay-to-Think Table")
    st.caption(PITCH)

    with st.sidebar:
        st.header("House rules")
        current = current_game()
        rosters = roster_labels()
        roster = st.selectbox(
            "Agent roster",
            options=list(rosters),
            index=list(rosters).index(current.config.agent_roster),
            format_func=lambda value: rosters[value],
        )
        start = st.number_input("Starting stack S", value=current.config.start_bankroll, disabled=True)
        fee = st.number_input("Entry fee X", value=current.config.entrance_fee, disabled=True)
        dealer_h = st.number_input("Dealer contribution H", value=current.config.dealer_contribution, disabled=True)
        rounds = st.number_input("Season rounds", value=current.config.n_rounds, disabled=True)
        agendas = agenda_labels()
        agenda_options = list(agendas)
        strategy = st.selectbox(
            "Dealer agenda",
            options=agenda_options,
            index=agenda_options.index(current.config.strategy_number),
            format_func=lambda value: agendas[value],
        )
        seed = st.number_input("Run seed", 1, 999999, 260822, 1)
        bluffing = st.toggle("Enable bluffing", value=current.config.enable_bluffing)
        live = st.toggle("Live Mistral API", value=current.config.use_live_api)
        solver_backend = st.selectbox(
            "Solver backend",
            options=["vibe_cli", "direct_sdk"],
            index=["vibe_cli", "direct_sdk"].index(
                getattr(current.config, "solver_backend", "vibe_cli")
            ),
            format_func=lambda value: "Vibe CLI" if value == "vibe_cli" else "Direct SDK",
        )
        show_traces = st.toggle("Show dealer traces", value=True)
        st.caption("Reasoning prices Y: none $1, low $2, medium $3, high $5, xhigh $9.")
        direct_client = st.session_state.get("client")
        if direct_client is None or not hasattr(direct_client, "available"):
            direct_client = MistralClient()
            st.session_state.client = direct_client
        vibe_client = st.session_state.get("vibe_client")
        if vibe_client is None or not hasattr(vibe_client, "available"):
            vibe_client = VibeCliClient()
            st.session_state.vibe_client = vibe_client
        active_client = vibe_client if solver_backend == "vibe_cli" else direct_client
        if live and not active_client.available:
            st.warning("No MISTRAL_API_KEY. Seeded chips still play.")
        if st.button("New table", width="stretch"):
            init_state(
                GameConfig(
                    start_bankroll=int(start),
                    entrance_fee=int(fee),
                    dealer_contribution=int(dealer_h),
                    agent_roster=roster,
                    n_rounds=int(rounds),
                    strategy_number=int(strategy),
                    seed=int(seed),
                    use_live_api=live,
                    solver_backend=solver_backend,
                    enable_bluffing=bluffing,
                )
            )
            st.rerun()

    game = current_game()
    autoplay_active = bool(st.session_state.get("autoplay")) and not game.finished
    if autoplay_active and not st.session_state.get("round_error"):
        run_one()
        game = current_game()
        if game.finished or st.session_state.get("round_error"):
            st.session_state.autoplay = False

    a, b, c, d = st.columns(4)
    a.metric("Hand", f"{min(game.round_index, game.config.n_rounds)} / {game.config.n_rounds}")
    b.metric("Rollover", game.prize_pool)
    c.metric("Entry X", game.config.entrance_fee)
    d.metric("Dealer H", game.config.dealer_contribution)

    if st.button("Auto-play 25 hands", type="primary", disabled=game.finished or autoplay_active):
        st.session_state.autoplay = True
        st.rerun()

    last = st.session_state.get("last")
    if st.session_state.get("round_error"):
        st.error(st.session_state.round_error)
    _poker_table(last if last and last.get("round") else None, game)

    if show_traces and last and last.get("round"):
        _dealer_panel(last)

    _scoreboard(game)
    if game.finished:
        _final(game)
    if st.session_state.get("autoplay") and not game.finished and not st.session_state.get("round_error"):
        time.sleep(0.35)
        st.rerun()


def _names(game: GameState) -> tuple[str, ...]:
    return tuple(game.display_names[agent_id] for agent_id in game.player_ids)


def _money(value: object) -> str:
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return str(value)
    if amount.is_integer():
        return f"${int(amount)}"
    return f"${amount:.2f}"


def _player_view(record: dict, name: str, game: GameState) -> dict:
    entry = next(e for e in record["phase1"]["entries"] if e["agent"] == name)
    last_action = "SIT OUT" if entry["decision"] == "DECLINE" else "ANTE"
    think = 0
    answer = ""
    correct = None
    for cycle in record.get("cycles") or []:
        for row in cycle["public"]["actions"]:
            if row["agent"] == name:
                last_action = row["action"]
                think += row.get("think_credits") or 0
        for row in cycle["dealer"]:
            if row["agent"] == name and row.get("answer"):
                answer = row["answer"]
                correct = bool(row.get("correct"))
    return {
        "name": name,
        "stack": game.bankrolls[name],
        "thinking": _thinking_label_for_name(game, name),
        "entered": entry["decision"] == "ENTER",
        "action": last_action,
        "think": think,
        "answer": answer,
        "correct": correct,
        "winner": name in (record.get("winners") or []),
    }


def _thinking_label_for_name(game: GameState, name: str) -> str:
    for agent_id, display_name in game.display_names.items():
        if display_name == name:
            return game.thinking_labels.get(agent_id, "")
    return ""


def _seat_html(p: dict, pos: str) -> str:
    klass = "seat seat-pos"
    if p.get("winner"):
        klass += " winner"
    elif p.get("entered") is False:
        klass += " folded"
    raw_answer = p.get("answer")
    if raw_answer:
        mark = "✓" if p.get("correct") else "✕"
        mark_class = "ok" if p.get("correct") else "no"
        ans_html = (
            f'<div class="seat-ans">answer: {html.escape(str(raw_answer))} '
            f'<span class="mark {mark_class}">{mark}</span></div>'
        )
    else:
        ans_html = '<div class="seat-ans">answer: —</div>'
    style = f"--seat-x:{pos[0]}%;--seat-y:{pos[1]}%;"
    emoji = SEAT_EMOJI.get(p["name"], "●")
    avatar = _seat_avatar(p)
    return f"""<div class="{klass}" style="{style}">
      <div class="seat-head">
        {avatar}
        <div>
          <div class="seat-name">{emoji} {html.escape(p['name'])}</div>
          <div class="seat-role">{html.escape(str(p.get('thinking') or ''))}</div>
        </div>
      </div>
      <div class="seat-stack">Total: {_money(p['stack'])}</div>
      <div class="seat-think">Cost: {_money(p.get('think') or 0)}</div>
      {ans_html}
    </div>"""


def _seat_avatar(p: dict) -> str:
    key = _portrait_key(str(p.get("thinking") or ""))
    path = PORTRAIT_ROOT / f"{key}.png"
    if not path.exists():
        return '<div class="seat-avatar"></div>'
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f'<img class="seat-avatar" src="data:image/png;base64,{data}" alt="">'


def _portrait_key(thinking: str) -> str:
    match thinking:
        case "Always thinker":
            return "always_think"
        case "No thinker":
            return "fast"
        case _:
            return "dynamic"


def _poker_table(record: dict | None, game: GameState) -> None:
    names = _names(game)
    positions = _seat_positions(len(names))
    if record:
        seats = "".join(
            _seat_html(_player_view(record, name, game), positions[index])
            for index, name in enumerate(names)
        )
        ann = record["announcement"]
        q = html.escape(record["problem"]["question"])
        pot = record["prize"]
        meta = f"Hand {record['round']}"
        if record.get("winners"):
            footer = f"Showdown · answer {html.escape(str(record['problem']['answer']))}"
        else:
            footer = f"No winner · pot rolls {record.get('rollover', 0)}"
        board = f'<div class="problem-meta">Board</div>{q}<div class="dealer-answer">{footer}</div>'
    else:
        seats = "".join(
            _seat_html(
                {
                    "name": name,
                    "stack": game.bankrolls[name],
                    "thinking": _thinking_label_for_name(game, name),
                    "entered": None,
                    "action": "waiting",
                    "think": 0,
                    "answer": "",
                    "winner": False,
                },
                positions[index],
            )
            for index, name in enumerate(names)
        )
        pot = game.prize_pool
        meta = "Waiting for the deal"
        board = '<div class="problem-meta">Board</div>Ante up.'

    st.markdown(
        f"""
<div class="room">
  {_dealer_html()}
  {seats}
  <div class="table">
    <div class="table-center">
      <div class="felt-top">{meta}</div>
      <div class="pot-chip">POT {_money(pot)}</div>
      <div class="problem-card">{board}</div>
    </div>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )


def _seat_positions(count: int) -> list[tuple[float, float]]:
    if count <= 0:
        return []
    import math

    center_x = 50
    center_y = 56
    radius_x = 31
    radius_y = 34
    start = -math.pi / 2 + math.pi / count
    lowest = max(
        center_y + radius_y * math.sin(start + 2 * math.pi * index / count)
        for index in range(count)
    )
    positions = []
    for index in range(count):
        angle = start + 2 * math.pi * index / count
        x = center_x + radius_x * math.cos(angle)
        y = center_y + radius_y * math.sin(angle)
        if y < lowest - 1:
            y += 11
        positions.append((x, y))
    return positions


def _dealer_html() -> str:
    path = PORTRAIT_ROOT / "dealer.png"
    if path.exists() and path.stat().st_size > 0:
        data = base64.b64encode(path.read_bytes()).decode("ascii")
        face = f'<img src="data:image/png;base64,{data}" alt="Dealer">'
    else:
        face = '<div class="seat-avatar"></div>'
    return f'<div class="dealer-cat">{face}<div class="label">Dealer</div></div>'


def _answer_rail(record: dict) -> None:
    official = html.escape(str(record["problem"]["answer"]))
    cards = []
    game = current_game()
    for name in _names(game):
        answers = []
        for cycle in record.get("cycles") or []:
            for row in cycle["dealer"]:
                if row["agent"] == name:
                    answers.append(row)
        if not answers:
            cards.append(
                f'<div class="hole"><div class="who">{html.escape(name)}</div>'
                f'<div class="tag">out</div></div>'
            )
            continue
        last = next((r for r in reversed(answers) if r.get("answer")), answers[-1])
        ans = last.get("answer") or "—"
        ok = bool(last.get("correct"))
        tag = "WIN" if name in record.get("winners", []) else ("hit" if ok else "miss")
        klass = "ok" if ok else "no"
        extra = ""
        if "Scientist" in name:
            trace = (last.get("dealer") or {}).get("trace") or {}
            if trace:
                extra = (
                    f'<div class="tag">{html.escape(str(trace.get("cheap_answer")))} → '
                    f'{html.escape(str(trace.get("deep_answer") or ans))} · '
                    f'{"PAY" if trace.get("pay_to_think") else "KEEP"}</div>'
                )
        cards.append(
            f'<div class="hole"><div class="who">{SEAT_EMOJI.get(name, "●")} {html.escape(name)}</div>'
            f'<div class="ans">{html.escape(str(ans))}</div>'
            f'<div class="tag {klass}">{tag} · {last.get("think_credits", 0)}c</div>{extra}</div>'
        )
    st.markdown(
        f'<div class="rail"><h3>Rail · answer {official}</h3>{"".join(cards)}</div>',
        unsafe_allow_html=True,
    )


def _bluff_log(record: dict) -> None:
    items = []
    for entry in record.get("phase1", {}).get("entries", []):
        name = str(entry.get("agent") or "Agent")
        message = str(entry.get("message") or "...")
        items.append(
            f'<div class="talk-item"><div class="talk-who">{SEAT_EMOJI.get(name, "●")} '
            f'{html.escape(name)}</div><div class="talk-msg">{html.escape(message)}</div></div>'
        )
    st.markdown(
        f'<div class="talk-log"><h3>Sequential bluffs</h3><div class="talk-grid">{"".join(items)}</div></div>',
        unsafe_allow_html=True,
    )


def _dealer_panel(record: dict) -> None:
    with st.expander("Full dealer traces", expanded=False):
        event = record.get("dealer_event") or {}
        if event:
            st.write(
                {
                    "hidden_difficulty": event.get("hidden_difficulty"),
                    "hidden_guessability": event.get("hidden_guessability"),
                    "problem_bank_sha256": event.get("problem_bank_sha256"),
                    "agenda_sha256": event.get("agenda_sha256"),
                    "reasoning_mapping_version": event.get("reasoning_mapping_version"),
                }
            )
        for cycle in record.get("cycles") or []:
            st.markdown(f"**Routing and solving** — {cycle['public']['dealer_announcement']}")
            for entry in cycle["dealer"]:
                st.write(
                    f"{entry['agent']}: {entry.get('tier')} "
                    f"(${entry['think_credits']} Y) → `{entry['answer'] or '—'}`"
                )
                if entry["agent"] == "Dynamic" and entry.get("dealer", {}).get("trace"):
                    _dynamic_trace(entry["dealer"]["trace"])


def _dynamic_trace(trace: dict) -> None:
    st.markdown(
        f"""
Cheap `{trace.get('cheap_answer')}` · probes {', '.join(str(a) for a in (trace.get('perturbed_answers') or []))}
Stability **{trace.get('stability')}** · {'PAY TO THINK' if trace.get('pay_to_think') else 'KEEP CHEAP'}
Deep `{trace.get('deep_answer') or '—'}` · changed {trace.get('changed_answer')}
        """
    )


def _scoreboard(game: GameState) -> None:
    st.subheader("Chip counts")
    rows = []
    for name in _names(game):
        s = game.stats[name]
        rows.append(
            {
                "seat": name,
                "thinker type": _thinking_label_for_name(game, name),
                "stack": s["bankroll"],
                "hands": s["rounds_played"],
                "folds": s["rounds_declined"],
                "showdown wins": s["correct"],
                "misses": s["incorrect"],
                "credits spent": s["credits_spent"],
                "pots won": s["prize_won"],
                "net": s["net_profit"],
                "accuracy": round(s["accuracy"], 2),
                "pot / credit": round(s["reward_per_credit"], 2),
            }
        )
    st.dataframe(rows, width="stretch", hide_index=True)


def _final(game: GameState) -> None:
    rec = game.history[-1] if game.history else {}
    sm = rec.get("final_summary") or {}
    st.subheader("Table closed")
    a, b, c, d = st.columns(4)
    a.metric("Chip leader", sm.get("winner", "—"))
    b.metric("Most accurate", sm.get("most_accurate", "—"))
    c.metric("Most efficient", sm.get("most_efficient", "—"))
    d.metric("Dynamic pay rate", f"{sm.get('dynamic_trigger_rate', 0):.0%}")
    rev = sm.get("best_revision")
    if rev:
        st.info(
            f"Best pay-to-think: `{rev['cheap']}` → `{rev['deep']}` on {rev['problem_id']}."
        )


if __name__ == "__main__":
    main()
