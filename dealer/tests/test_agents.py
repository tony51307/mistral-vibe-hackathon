from dataclasses import asdict
from pathlib import Path
import tempfile
import unittest

import yaml

from game.agent_config import (
    AgentConfigError,
    RuntimeKind,
    load_agent_catalog,
    prepare_agent_context,
    resolve_llm_runtime,
)
from game.dealer_distributor import DealerGame
from game.loaders import load_agendas, load_problem_bank


ROOT = Path(__file__).resolve().parents[1]
AGENT_PATH = ROOT / "agents" / "agent_rosters_v1.yaml"
BANK = load_problem_bank(ROOT / "data" / "pay_to_think_problem_bank_v1.json")
AGENDAS = load_agendas(ROOT / "data" / "pay_to_think_agendas_v1.yaml", BANK)


def all_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from all_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from all_keys(child)


class AgentConfigurationTests(unittest.TestCase):
    def test_profiles_and_every_six_to_ten_agent_roster_load(self):
        catalog = load_agent_catalog(AGENT_PATH)
        self.assertEqual(len(catalog.profiles), 10)
        self.assertEqual(
            {roster.initial_agent_count for roster in catalog.rosters.values()},
            {6, 7, 8, 9, 10},
        )
        for count in range(6, 11):
            roster = catalog.get_roster(f"social_{count}")
            self.assertEqual(len(roster.seats), count)
            self.assertEqual(len(set(roster.player_ids())), count)
        social_six = catalog.get_roster("social_6")
        self.assertTrue(
            all(
                catalog.profiles[seat.profile_id].runtime_kind == RuntimeKind.LLM
                for seat in social_six.seats
            )
        )
        self.assertEqual(
            {
                catalog.profiles[seat.profile_id].bluff.mode
                for seat in social_six.seats
            },
            {"none", "honest", "strategic"},
        )

    def test_llm_runtime_resolves_environment_without_returning_secret(self):
        catalog = load_agent_catalog(AGENT_PATH)
        profile = catalog.get_profile("scientist")
        runtime = resolve_llm_runtime(
            profile,
            {"MISTRAL_MODEL": "configured-model", "MISTRAL_API_KEY": "secret-value"},
        )
        self.assertEqual(profile.runtime_kind, RuntimeKind.LLM)
        self.assertEqual(runtime.model_id, "configured-model")
        self.assertEqual(runtime.api_key_env, "MISTRAL_API_KEY")
        self.assertNotIn("secret-value", asdict(runtime).values())

    def test_llm_runtime_reports_missing_environment_by_name(self):
        profile = load_agent_catalog(AGENT_PATH).get_profile("scientist")
        with self.assertRaisesRegex(AgentConfigError, "MISTRAL_MODEL"):
            resolve_llm_runtime(profile, {})
        with self.assertRaisesRegex(AgentConfigError, "MISTRAL_API_KEY"):
            resolve_llm_runtime(profile, {"MISTRAL_MODEL": "configured-model"})

    def test_deterministic_profile_cannot_resolve_as_llm(self):
        profile = load_agent_catalog(AGENT_PATH).get_profile("monk")
        with self.assertRaisesRegex(AgentConfigError, "not LLM-driven"):
            resolve_llm_runtime(profile, {})

    def test_social_blind_context_removes_current_and_historical_talk(self):
        catalog = load_agent_catalog(AGENT_PATH)
        scientist = catalog.get_profile("scientist")
        source = {
            "public_messages": {"bluffer": "Going xhigh."},
            "public_history": [
                {
                    "round": 1,
                    "table_talk": [{"agent_id": "bluffer", "message": "Easy."}],
                    "agents": [],
                }
            ],
        }
        prepared = prepare_agent_context(source, scientist)
        self.assertNotIn("public_messages", prepared)
        self.assertNotIn("table_talk", prepared["public_history"][0])
        self.assertIn("public_messages", source)
        self.assertIn("table_talk", source["public_history"][0])

    def test_roster_builds_dealer_with_fixed_economy_and_metadata(self):
        catalog = load_agent_catalog(AGENT_PATH)
        game = DealerGame.from_agent_roster(
            agent_catalog=catalog,
            roster_id="social_10",
            problem_bank=BANK,
            agenda_catalog=AGENDAS,
            seed=260822,
        )
        self.assertEqual(len(game.players), 10)
        self.assertEqual(game.config.dealer_contribution_cents, 3_000)
        self.assertEqual(game.agenda.strategy_number, 3)
        self.assertEqual(game.agent_roster_id, "social_10")
        self.assertEqual(game.agent_metadata["darwin"]["bluff_mode"], "learned")

    def test_round_event_and_next_payload_expose_only_public_social_history(self):
        catalog = load_agent_catalog(AGENT_PATH)
        game = DealerGame.from_agent_roster(
            agent_catalog=catalog,
            roster_id="social_6",
            problem_bank=BANK,
            agenda_catalog=AGENDAS,
            seed=260822,
        )
        category_payloads = game.reveal_category()
        self.assertEqual(len(category_payloads["prodigy"]["opponent_bankrolls_cents"]), 5)
        game.collect_entries()
        game.record_table_talk(
            {agent_id: f"{agent_id} category signal" for agent_id in category_payloads}
        )
        problem_payloads = game.reveal_problem()
        game.route_and_purchase(
            {
                agent_id: (lambda payload: {"reasoning_tier": "none"})
                for agent_id in problem_payloads
            }
        )
        problem_id = problem_payloads["prodigy"]["problem_id"]
        correct = BANK.problems[problem_id]["answer"]["display"]
        game.solve(
            {
                agent_id: (lambda payload, answer=correct: {"answer": answer})
                for agent_id in problem_payloads
            }
        )
        game.judge()
        game.payout()
        event = game.complete_round()

        self.assertEqual(event["agent_roster_id"], "social_6")
        self.assertEqual(len(event["table_talk"]), 6)
        self.assertEqual(event["agents"][4]["profile_id"], "bluffer")
        next_payload = game.reveal_category()["prodigy"]
        self.assertEqual(len(next_payload["public_history"]), 1)
        forbidden = {
            "answer_key",
            "correct_answer",
            "hidden_difficulty",
            "hidden_guessability",
            "dealer_meta",
            "validator",
            "chain_of_thought",
            "private_strategy",
            "internal_confidence",
        }
        self.assertFalse(forbidden & set(all_keys(next_payload["public_history"])))

    def test_roster_with_unknown_profile_is_rejected(self):
        document = yaml.safe_load(AGENT_PATH.read_text(encoding="utf-8"))
        document["rosters"][0]["seats"][0]["profile_id"] = "missing"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "agents.yaml"
            path.write_text(yaml.safe_dump(document), encoding="utf-8")
            with self.assertRaisesRegex(AgentConfigError, "unknown profile_id"):
                load_agent_catalog(path)


if __name__ == "__main__":
    unittest.main()
