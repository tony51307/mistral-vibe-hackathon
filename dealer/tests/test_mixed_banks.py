import json
from pathlib import Path
import tempfile
import unittest

import yaml

from game.dealer_distributor import DealerGame
from game.judge import judge_answer
from game.loaders import (
    DataValidationError,
    load_agenda_catalogs,
    load_agendas,
    load_problem_banks,
    load_table_modes,
)
from game.models import GameConfig, ReasoningTier


ROOT = Path(__file__).resolve().parents[1]
OLD_BANK_PATH = ROOT / "data" / "pay_to_think_problem_bank_v1.json"
NEW_BANK_PATH = ROOT / "data" / "pay_to_think_reasoning_sensitive_additions_v2.json"
OLD_AGENDA_PATH = ROOT / "data" / "pay_to_think_agendas_v1.yaml"
NEW_AGENDA_PATH = ROOT / "data" / "pay_to_think_mixed_old_new_agendas_v3.yaml"
TABLE_PATH = ROOT / "tables" / "table_modes_v1.yaml"


class MixedBankTests(unittest.TestCase):
    def setUp(self):
        self.bank = load_problem_banks([OLD_BANK_PATH, NEW_BANK_PATH])

    def test_two_banks_merge_with_disjoint_ids_and_provenance(self):
        self.assertEqual(len(self.bank.problems), 92)
        self.assertEqual(
            set(self.bank.source_sha256s),
            {OLD_BANK_PATH.name, NEW_BANK_PATH.name},
        )
        self.assertEqual(
            self.bank.source_by_problem_id["quant_001"],
            OLD_BANK_PATH.name,
        )
        self.assertEqual(
            self.bank.source_by_problem_id["ptt2_math_001"],
            NEW_BANK_PATH.name,
        )

    def test_v3_agendas_validate_source_and_reasoning_metadata(self):
        catalog = load_agendas(NEW_AGENDA_PATH, self.bank)
        self.assertEqual(set(catalog.agendas), {11, 12, 13, 14, 15})
        self.assertTrue(all(len(agenda.rounds) == 25 for agenda in catalog.agendas.values()))
        first = catalog.agendas[12].rounds[0]
        self.assertEqual(first.problem_id, "ptt2_math_001")
        self.assertEqual(first.source_bank, "new_v2")
        self.assertEqual(first.reasoning_profile, "reasoning_sensitive_low")
        self.assertEqual(first.reference_reasoning_tier, ReasoningTier.LOW)

    def test_old_and_new_agenda_catalogs_merge_deterministically(self):
        forward = load_agenda_catalogs([OLD_AGENDA_PATH, NEW_AGENDA_PATH], self.bank)
        reverse = load_agenda_catalogs([NEW_AGENDA_PATH, OLD_AGENDA_PATH], self.bank)
        self.assertEqual(set(forward.agendas), set(range(1, 16)))
        self.assertEqual(forward.sha256, reverse.sha256)
        tables = load_table_modes(TABLE_PATH, forward)
        self.assertEqual(tables.get("tournament").initial_agent_count, 8)

    def test_duplicate_problem_ids_across_banks_are_rejected(self):
        document = json.loads(NEW_BANK_PATH.read_text(encoding="utf-8"))
        document["problems"][0]["id"] = "quant_001"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / NEW_BANK_PATH.name
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(DataValidationError, "duplicate problem id across banks"):
                load_problem_banks([OLD_BANK_PATH, path])

    def test_duplicate_json_and_yaml_keys_are_rejected(self):
        bank_text = NEW_BANK_PATH.read_text(encoding="utf-8")
        duplicate_bank = bank_text.replace(
            '"schema_version": "2.0",',
            '"schema_version": "2.0",\n  "schema_version": "2.0",',
            1,
        )
        agenda_text = NEW_AGENDA_PATH.read_text(encoding="utf-8")
        duplicate_agenda = agenda_text.replace(
            "schema_version: '3.0'",
            "schema_version: '3.0'\nschema_version: '3.0'",
            1,
        )
        with tempfile.TemporaryDirectory() as directory:
            bank_path = Path(directory) / NEW_BANK_PATH.name
            agenda_path = Path(directory) / NEW_AGENDA_PATH.name
            bank_path.write_text(duplicate_bank, encoding="utf-8")
            agenda_path.write_text(duplicate_agenda, encoding="utf-8")
            with self.assertRaisesRegex(DataValidationError, "duplicate JSON key"):
                load_problem_banks([bank_path])
            with self.assertRaisesRegex(DataValidationError, "duplicate YAML key"):
                load_agendas(agenda_path, self.bank)

    def test_duplicate_strategy_numbers_across_catalogs_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate_agendas.yaml"
            path.write_text(OLD_AGENDA_PATH.read_text(encoding="utf-8"), encoding="utf-8")
            with self.assertRaisesRegex(DataValidationError, "duplicate strategy_number"):
                load_agenda_catalogs([OLD_AGENDA_PATH, path], self.bank)

    def test_v3_source_bank_mismatch_is_rejected(self):
        document = yaml.safe_load(NEW_AGENDA_PATH.read_text(encoding="utf-8"))
        document["agendas"][0]["rounds"][0]["source_bank"] = "new_v2"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / NEW_AGENDA_PATH.name
            path.write_text(yaml.safe_dump(document), encoding="utf-8")
            with self.assertRaisesRegex(DataValidationError, "source_bank mismatch"):
                load_agendas(path, self.bank)

    def test_every_new_display_answer_is_accepted(self):
        for problem_id, problem in self.bank.problems.items():
            if not problem_id.startswith("ptt2_"):
                continue
            with self.subTest(problem_id=problem_id):
                result = judge_answer(problem, problem["answer"]["display"])
                self.assertTrue(result.correct, result.error)

    def test_mixed_metadata_is_hidden_from_agents_and_written_to_audit(self):
        agendas = load_agenda_catalogs([OLD_AGENDA_PATH, NEW_AGENDA_PATH], self.bank)
        game = DealerGame(
            player_ids=["agent"],
            problem_bank=self.bank,
            agenda_catalog=agendas,
            strategy_number=12,
            seed=260822,
            config=GameConfig(season_rounds=1),
        )
        category = game.reveal_category()["agent"]
        self.assertNotIn("source_bank", category)
        self.assertNotIn("reasoning_profile", category)
        game.collect_entries()
        game.record_table_talk({})
        problem_payload = game.reveal_problem()["agent"]
        self.assertEqual(
            set(problem_payload) & {"problem_id", "category", "prompt_markdown"},
            {"problem_id", "category", "prompt_markdown"},
        )
        self.assertNotIn("source_bank", problem_payload)
        self.assertNotIn("reasoning_profile", problem_payload)
        game.route_and_purchase({"agent": lambda payload: {"reasoning_tier": "none"}})
        answer = self.bank.problems[problem_payload["problem_id"]]["answer"]["display"]
        game.solve({"agent": lambda payload: {"answer": answer}})
        game.judge()
        game.payout()
        event = game.complete_round()
        self.assertEqual(event["hidden_source_bank"], "new_v2")
        self.assertEqual(event["hidden_reasoning_profile"], "reasoning_sensitive_low")
        self.assertEqual(event["hidden_reference_reasoning_tier"], "low")
        self.assertEqual(set(event["problem_bank_source_sha256s"]), {
            OLD_BANK_PATH.name,
            NEW_BANK_PATH.name,
        })


if __name__ == "__main__":
    unittest.main()
