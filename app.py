from __future__ import annotations

import streamlit as st

from game import GameEngine, SeasonState
from metrics import agent_scoreboard, bankroll_series, economy_metrics


st.set_page_config(page_title="Pay-to-Think Arena", layout="wide")


def get_state() -> tuple[GameEngine, SeasonState]:
    if "engine" not in st.session_state:
        st.session_state.engine = GameEngine(seed=7, use_mistral=False)
        st.session_state.season = st.session_state.engine.new_season()
    return st.session_state.engine, st.session_state.season


def reset(seed: int, use_mistral: bool) -> None:
    st.session_state.engine = GameEngine(seed=seed, use_mistral=use_mistral)
    st.session_state.season = st.session_state.engine.new_season()


engine, season = get_state()

st.title("Pay-to-Think Dealer Economy")
st.caption("V1 economy with fixed entry fees, burned reasoning spend, dealer contribution, rollover, and AutoThink routing.")

with st.sidebar:
    st.header("Controls")
    seed = st.number_input("Seed", min_value=1, max_value=9999, value=season.seed)
    use_mistral = st.toggle("Use Mistral API", value=engine.use_mistral)
    if st.button("Reset season", use_container_width=True):
        reset(int(seed), use_mistral)
        st.rerun()
    if st.button("Run one round", use_container_width=True):
        engine.play_next_round(season)
        st.rerun()
    if st.button("Run to end", use_container_width=True):
        while season.round_number < season.config.season_rounds:
            engine.play_next_round(season)
        st.rerun()

config = season.config
cols = st.columns(5)
cols[0].metric("Round", f"{season.round_number}/{config.season_rounds}")
cols[1].metric("Entry X", f"${config.entry_fee}")
cols[2].metric("Dealer H", f"${config.dealer_contribution}")
cols[3].metric("Jackpot", f"${season.rollover:.0f}")
cols[4].metric("Money Supply", f"${economy_metrics(season)['money_supply']:.0f}")

st.subheader("Scoreboard")
st.dataframe(agent_scoreboard(season), use_container_width=True, hide_index=True)

if season.history:
    latest = season.history[-1]
    st.subheader(f"Round {latest.round_id}: {latest.category.title()}")

    top = st.columns([2, 1])
    with top[0]:
        st.markdown(f"**Problem:** {latest.problem.question}")
        st.markdown(f"**Answer:** `{latest.problem.answer}`")
        st.markdown(f"**Explanation:** {latest.problem.explanation}")
    with top[1]:
        st.metric("Pot", f"${latest.pot:.0f}")
        st.metric("Rollover In", f"${latest.rollover_in:.0f}")
        st.metric("Rollover Out", f"${latest.rollover_out:.0f}")

    st.markdown("**Table Talk**")
    st.dataframe(
        [{"agent": season.agents[agent_id].name, "message": message} for agent_id, message in latest.public_messages.items()],
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("**Answers**")
    st.dataframe(
        [
            {
                "agent": season.agents[agent_id].name,
                "tier": turn.reasoning_tier,
                "cost": turn.reasoning_cost,
                "answer": turn.submitted_answer,
                "correct": agent_id in latest.correct_agents,
                "show_hand": turn.show_hand,
            }
            for agent_id, turn in latest.turns.items()
        ],
        use_container_width=True,
        hide_index=True,
    )

    auto_turn = latest.turns.get("auto")
    if auto_turn and auto_turn.routing_decision:
        decision = auto_turn.routing_decision
        st.subheader("AutoThink Trace")
        trace_cols = st.columns(5)
        trace_cols[0].metric("AutoThink", decision.autothink_level)
        trace_cols[1].metric("Agreement", decision.decision_agreement)
        trace_cols[2].metric("Risk", decision.risk)
        trace_cols[3].metric("Tier", decision.reasoning_tier)
        trace_cols[4].metric("Probe Tokens", decision.probe_cost_tokens)
        st.json(
            {
                "baseline_decision": decision.baseline_decision,
                "critical_perspective_decision": decision.critical_perspective_decision,
                "reason": decision.reason,
                "trace": decision.trace,
            }
        )
else:
    st.info("Run one round to start the season.")

st.subheader("Economy Health")
st.json(economy_metrics(season))

series = bankroll_series(season)
if series:
    st.line_chart(series, x="round", y="bankroll", color="agent")

