"""Pay-to-Think math bidding demo — Streamlit poker-table UI."""

from __future__ import annotations

import html

import streamlit as st

from game import GameConfig, GameState, new_game, play_round
from mistral_client import MistralClient


st.set_page_config(page_title="Pay-to-Think Table", layout="wide")

NAMES = ("Fast", "Always Think", "Dynamic", "Control")
SEAT_EMOJI = {"Fast": "⚡", "Always Think": "🧠", "Dynamic": "🎯", "Control": "⚖️"}

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
  height: 640px;
  background:
    radial-gradient(circle at 50% 45%, #3a2818 0%, #1a100a 75%);
  border-radius: 18px;
  overflow: hidden;
  font-family: 'IBM Plex Sans', sans-serif;
  color: #f4efe4;
}
.table {
  position: absolute;
  left: 50%;
  top: 52%;
  width: min(520px, 70%);
  height: min(520px, 78%);
  transform: translate(-50%, -50%);
  border-radius: 50%;
  background:
    radial-gradient(circle at 50% 42%, #2a8a4a 0%, #145c2e 55%, #0a3318 100%);
  border: 18px solid #6b3e14;
  box-shadow:
    inset 0 0 0 8px #d4af37,
    inset 0 0 70px rgba(0,0,0,.35),
    0 18px 40px rgba(0,0,0,.45);
}
.table-center {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  width: 62%;
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
  padding: 6px 18px;
  font-weight: 700;
  font-size: 20px;
}
.problem-card {
  margin: 10px auto 0;
  background: #fffaf0;
  color: #1a1208;
  border-radius: 8px;
  padding: 10px 12px;
  font-family: 'Libre Baskerville', serif;
  font-size: 13px;
  line-height: 1.35;
  max-height: 150px;
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
  width: 168px;
  background: #140e0a;
  border: 2px solid #c9a227;
  border-radius: 14px;
  padding: 10px 12px;
  z-index: 3;
  box-shadow: 0 8px 18px rgba(0,0,0,.4);
}
.seat.winner { box-shadow: 0 0 0 3px #f5d76e, 0 8px 18px rgba(0,0,0,.4); }
.seat.folded { opacity: .5; }
.seat-top { left: 50%; top: 10px; transform: translateX(-50%); }
.seat-bottom { left: 50%; bottom: 10px; transform: translateX(-50%); }
.seat-left { left: 14px; top: 58%; transform: translateY(-50%); }
.seat-right { right: 14px; top: 58%; transform: translateY(-50%); }
.seat-name { font-weight: 700; font-size: 15px; }
.seat-stack { color: #b7e4c7; font-size: 12px; margin: 3px 0 6px; }
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
  font-size: 18px;
}
.seat-think { font-size: 11px; color: #ddd; margin-top: 4px; }
.dealer-key { margin-top: 8px; font-size: 11px; color: #d8c27a; }
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
  font-size: 11px;
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
</style>
"""


def init_state(config: GameConfig) -> None:
    st.session_state.game = new_game(config)
    st.session_state.client = MistralClient()
    st.session_state.last = None


def current_game() -> GameState:
    return st.session_state.game


def run_one() -> None:
    st.session_state.last = play_round(current_game(), st.session_state.client)


def run_all() -> None:
    g = current_game()
    while not g.finished:
        st.session_state.last = play_round(g, st.session_state.client)


def main() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    if "game" not in st.session_state:
        init_state(GameConfig())

    st.title("Pay-to-Think Table")
    st.caption(PITCH)

    with st.sidebar:
        st.header("House rules")
        start = st.number_input("Starting stack S", 20, 500, 80, 10)
        fee = st.number_input("Entry fee X", 1, 20, 10, 1)
        dealer_h = st.number_input("Dealer contribution H", 1, 50, 12, 1)
        rounds = st.number_input("Season rounds", 5, 25, 25, 1)
        strategy = st.selectbox(
            "Dealer agenda",
            options=[1, 2, 3, 4, 5],
            index=2,
            format_func=lambda value: f"Strategy {value}",
        )
        seed = st.number_input("Run seed", 1, 999999, 260822, 1)
        live = st.toggle("Live Mistral API", value=False)
        show_traces = st.toggle("Show dealer traces", value=True)
        st.caption("Reasoning prices Y: none $1, low $2, medium $3, high $5, xhigh $9.")
        client = st.session_state.get("client") or MistralClient()
        if live and not client.available:
            st.warning("No MISTRAL_API_KEY. Seeded chips still play.")
        if st.button("New table", use_container_width=True):
            init_state(
                GameConfig(
                    start_bankroll=int(start),
                    entrance_fee=int(fee),
                    dealer_contribution=int(dealer_h),
                    n_rounds=int(rounds),
                    strategy_number=int(strategy),
                    seed=int(seed),
                    use_live_api=live,
                )
            )
            st.rerun()

    game = current_game()
    a, b, c, d = st.columns(4)
    a.metric("Hand", f"{min(game.round_index + (0 if game.finished else 1), game.config.n_rounds)} / {game.config.n_rounds}")
    b.metric("Rollover", game.prize_pool)
    c.metric("Entry X", game.config.entrance_fee)
    d.metric("Dealer H", game.config.dealer_contribution)

    x, y, _ = st.columns(3)
    if x.button("Deal next hand", type="primary", disabled=game.finished):
        run_one()
    if y.button("Run 10 hands", disabled=game.finished):
        run_all()

    last = st.session_state.get("last")
    if not (last and last.get("round")) and not game.finished:
        run_one()
        last = st.session_state.last
        st.rerun()

    table, rail = st.columns([2.2, 1])
    with table:
        _poker_table(last if last and last.get("round") else None, game)
    with rail:
        if last and last.get("round"):
            _answer_rail(last)
        else:
            st.markdown('<div class="rail"><h3>Dealer rail</h3><p>Waiting for a hand.</p></div>', unsafe_allow_html=True)
    if show_traces and last and last.get("round"):
        _dealer_panel(last)

    _scoreboard(game)
    if game.finished:
        _final(game)


def _player_view(record: dict, name: str, game: GameState) -> dict:
    entry = next(e for e in record["phase1"]["entries"] if e["agent"] == name)
    last_action = "SIT OUT" if entry["decision"] == "DECLINE" else "ANTE"
    think = 0
    answer = ""
    for cycle in record.get("cycles") or []:
        for row in cycle["public"]["actions"]:
            if row["agent"] == name:
                last_action = row["action"]
                think += row.get("think_credits") or 0
        for row in cycle["dealer"]:
            if row["agent"] == name and row.get("answer"):
                answer = row["answer"]
    return {
        "name": name,
        "stack": game.bankrolls[name],
        "entered": entry["decision"] == "ENTER",
        "action": last_action,
        "think": think,
        "answer": answer,
        "winner": name in (record.get("winners") or []),
    }


def _seat_html(p: dict, pos: str) -> str:
    klass = f"seat {pos}"
    if p.get("winner"):
        klass += " winner"
    elif p.get("entered") is False:
        klass += " folded"
    action = p.get("action") or "—"
    if p.get("entered") and p.get("action") == "THINK":
        action = f"THINK {p.get('think', 0)}"
    elif p.get("entered") and p.get("action") == "ANTE":
        action = "IN"
    ans = html.escape(str(p.get("answer") or "—"))
    return f"""<div class="{klass}">
      <div class="seat-name">{SEAT_EMOJI[p['name']]} {html.escape(p['name'])}</div>
      <div class="seat-stack">Stack {p['stack']} · {'in' if p.get('entered') else 'out'}</div>
      <div class="seat-action">{html.escape(str(action))}</div>
      <div class="seat-ans">{ans}</div>
      <div class="seat-think">{p.get('think', 0)} think credits</div>
    </div>"""


def _poker_table(record: dict | None, game: GameState) -> None:
    positions = {
        "Always Think": "seat-top",
        "Fast": "seat-left",
        "Dynamic": "seat-right",
        "Control": "seat-bottom",
    }
    if record:
        seats = "".join(
            _seat_html(_player_view(record, name, game), positions[name]) for name in NAMES
        )
        ann = record["announcement"]
        q = html.escape(record["problem"]["question"])
        pot = record["prize"]
        meta = f"Hand {record['round']} · {html.escape(ann['category'])}"
        if record.get("winners"):
            footer = (
                f"Showdown · key {html.escape(str(record['problem']['answer']))} · "
                f"split {html.escape(str(record['payouts']))}"
            )
        else:
            footer = f"No winner · pot rolls {record.get('rollover', 0)}"
        board = f'<div class="problem-meta">Board</div>{q}<div class="dealer-key">{footer}</div>'
    else:
        seats = "".join(
            _seat_html(
                {"name": name, "stack": game.bankrolls[name], "entered": None, "action": "waiting", "think": 0, "answer": "", "winner": False},
                positions[name],
            )
            for name in NAMES
        )
        pot = game.prize_pool
        meta = "Waiting for the deal"
        board = '<div class="problem-meta">Board</div>Ante up.'

    st.markdown(
        f"""
<div class="room">
  {seats}
  <div class="table">
    <div class="table-center">
      <div class="felt-top">{meta}</div>
      <div class="pot-chip">POT {pot}</div>
      <div class="problem-card">{board}</div>
    </div>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )


def _answer_rail(record: dict) -> None:
    official = html.escape(str(record["problem"]["answer"]))
    cards = []
    for name in NAMES:
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
        if name == "Dynamic":
            trace = (last.get("dealer") or {}).get("trace") or {}
            if trace:
                extra = (
                    f'<div class="tag">{html.escape(str(trace.get("cheap_answer")))} → '
                    f'{html.escape(str(trace.get("deep_answer") or ans))} · '
                    f'{"PAY" if trace.get("pay_to_think") else "KEEP"}</div>'
                )
        cards.append(
            f'<div class="hole"><div class="who">{SEAT_EMOJI[name]} {html.escape(name)}</div>'
            f'<div class="ans">{html.escape(str(ans))}</div>'
            f'<div class="tag {klass}">{tag} · {last.get("think_credits", 0)}c</div>{extra}</div>'
        )
    st.markdown(
        f'<div class="rail"><h3>Rail · key {official}</h3>{"".join(cards)}</div>',
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
    for name in NAMES:
        s = game.stats[name]
        rows.append(
            {
                "seat": name,
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
    st.dataframe(rows, use_container_width=True, hide_index=True)


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
