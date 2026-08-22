from __future__ import annotations

from dataclasses import dataclass, field

from agents import AgentState, AgentTurn, answer_problem, default_agents, policy_for
from auto_thinking import RoutingContext, StubAutoThinkingAdapter
from economy import REASONING_PRICES, EconomyConfig, affordable_tiers
from event_log import AgentRoundEvent
from mistral_client import MistralClient, ModelProvider
from problems import Problem, is_correct, seeded_problem_sequence


@dataclass
class RoundResult:
    round_id: int
    problem: Problem
    category: str
    pot: float
    rollover_in: float
    rollover_out: float
    public_messages: dict[str, str]
    turns: dict[str, AgentTurn]
    correct_agents: list[str]
    events: list[AgentRoundEvent]


@dataclass
class SeasonState:
    season_id: str
    config: EconomyConfig = field(default_factory=EconomyConfig)
    seed: int = 7
    round_number: int = 0
    rollover: float = 0
    rollover_chain: int = 0
    agents: dict[str, AgentState] = field(default_factory=dict)
    history: list[RoundResult] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.agents:
            self.agents = default_agents(
                self.config.starting_bankroll, StubAutoThinkingAdapter()
            )


class GameEngine:
    def __init__(
        self,
        config: EconomyConfig | None = None,
        seed: int = 7,
        use_mistral: bool = False,
        model_provider: ModelProvider = "mistral",
    ) -> None:
        self.config = config or EconomyConfig()
        self.seed = seed
        self.auto_thinking = StubAutoThinkingAdapter()
        self.model_provider = model_provider
        self.mistral_client = MistralClient(model_provider)
        self.use_mistral = use_mistral
        self.problems = seeded_problem_sequence(seed, self.config.season_rounds)

    def new_season(self, season_id: str = "demo-season") -> SeasonState:
        return SeasonState(
            season_id=season_id,
            config=self.config,
            seed=self.seed,
            agents=default_agents(self.config.starting_bankroll, self.auto_thinking),
        )

    def play_next_round(  # noqa: PLR0914, PLR0915
        self, state: SeasonState
    ) -> RoundResult | None:
        if state.round_number >= self.config.season_rounds:
            return None

        problem = self.problems[state.round_number]
        round_id = state.round_number + 1
        public_messages: dict[str, str] = {}
        turns: dict[str, AgentTurn] = {}
        bankroll_before: dict[str, float] = {}

        active_agents = [
            agent
            for agent in state.agents.values()
            if not agent.eliminated and agent.bankroll > 0
        ]

        pot = state.rollover
        rollover_in = state.rollover
        state.rollover = 0

        for agent in active_agents:
            bankroll_before[agent.agent_id] = agent.bankroll
            policy = policy_for(agent, self.auto_thinking)
            public_messages[agent.agent_id] = policy.public_message(
                agent, problem.category
            )

        pot += self.config.dealer_contribution

        for agent in active_agents:
            policy = policy_for(agent, self.auto_thinking)
            show_hand = 0 < agent.bankroll < self.config.entry_fee
            entry_paid = 0.0

            if show_hand:
                entry_paid = agent.bankroll
                pot += entry_paid
                agent.bankroll = 0
                tier = "none"
                reasoning_cost = 0.0
                routing_decision = None
            else:
                entry_paid = float(self.config.entry_fee)
                agent.bankroll -= entry_paid
                pot += entry_paid

                context = RoutingContext(
                    agent_id=agent.agent_id,
                    category=problem.category,
                    problem=problem,
                    bankroll_after_entry=agent.bankroll,
                    pot=pot,
                    round_number=round_id,
                    public_messages=public_messages,
                    opponent_history={},
                    available_reasoning_tiers=affordable_tiers(agent.bankroll),
                    strategy_memory=agent.strategy_memory,
                    rollover_chain=state.rollover_chain,
                )
                tier, routing_decision = policy.choose_tier(
                    agent, agent.bankroll, context
                )
                reasoning_cost = float(REASONING_PRICES[tier])
                agent.bankroll -= reasoning_cost

            answer, telemetry = answer_problem(
                agent, problem, tier, round_id, self.mistral_client, self.use_mistral
            )
            turns[agent.agent_id] = AgentTurn(
                agent_id=agent.agent_id,
                public_message=public_messages.get(agent.agent_id, ""),
                entry_paid=entry_paid,
                show_hand=show_hand,
                reasoning_tier=tier,
                reasoning_cost=reasoning_cost,
                bankroll_after_reasoning=agent.bankroll,
                submitted_answer=answer,
                routing_decision=routing_decision,
                model_telemetry=telemetry,
            )

        correct_agents = [
            agent_id
            for agent_id, turn in turns.items()
            if is_correct(problem, turn.submitted_answer)
        ]
        prize_by_agent = {agent_id: 0.0 for agent_id in turns}
        rollover_out = 0.0

        if correct_agents:
            share = pot / len(correct_agents)
            for agent_id in correct_agents:
                state.agents[agent_id].bankroll += share
                prize_by_agent[agent_id] = share
            state.rollover_chain = 0
        else:
            rollover_out = pot
            state.rollover = pot
            state.rollover_chain += 1

        for agent in state.agents.values():
            if agent.bankroll <= 0 and agent.agent_id not in correct_agents:
                agent.eliminated = True

        events = [
            AgentRoundEvent(
                season_id=state.season_id,
                round_id=round_id,
                problem_id=problem.id,
                category=problem.category,
                hidden_difficulty=problem.hidden_difficulty,
                correct_answer=problem.answer,
                agent_id=agent_id,
                bankroll_before=bankroll_before.get(agent_id, 0.0),
                public_message=turn.public_message,
                entry_paid=turn.entry_paid,
                reasoning_tier=turn.reasoning_tier,
                reasoning_cost=turn.reasoning_cost,
                bankroll_after_reasoning=turn.bankroll_after_reasoning,
                submitted_answer=turn.submitted_answer,
                correct=agent_id in correct_agents,
                prize_received=prize_by_agent[agent_id],
                bankroll_after_round=state.agents[agent_id].bankroll,
                pot_before=pot,
                dealer_contribution=float(self.config.dealer_contribution),
                rollover_in=rollover_in,
                rollover_out=rollover_out,
                number_correct=len(correct_agents),
                show_hand=turn.show_hand,
                routing_trace=(
                    turn.routing_decision.trace
                    | {
                        "autothink_level": turn.routing_decision.autothink_level,
                        "decision_agreement": turn.routing_decision.decision_agreement,
                        "risk": turn.routing_decision.risk,
                        "reason": turn.routing_decision.reason,
                        "baseline_decision": turn.routing_decision.baseline_decision,
                        "critical_perspective_decision": turn.routing_decision.critical_perspective_decision,
                    }
                    if turn.routing_decision
                    else {}
                ),
                model_telemetry=turn.model_telemetry,
            )
            for agent_id, turn in turns.items()
        ]

        result = RoundResult(
            round_id=round_id,
            problem=problem,
            category=problem.category,
            pot=pot,
            rollover_in=rollover_in,
            rollover_out=rollover_out,
            public_messages=public_messages,
            turns=turns,
            correct_agents=correct_agents,
            events=events,
        )
        state.round_number = round_id
        state.history.append(result)
        return result
