from pathlib import Path
import unittest

from game.judge import judge_answer
from game.loaders import load_problem_bank


def problem(validator):
    return {"answer": {"validator": validator}}


class JudgeTests(unittest.TestCase):
    def test_every_canonical_display_answer_is_accepted(self):
        root = Path(__file__).resolve().parents[1]
        bank = load_problem_bank(root / "data" / "pay_to_think_problem_bank_v1.json")
        failures = [
            problem_id
            for problem_id, item in bank.problems.items()
            if not judge_answer(item, item["answer"]["display"]).correct
        ]
        self.assertEqual(failures, [])

    def test_numeric_fraction_and_decimal(self):
        item = problem({"kind": "numeric", "value": 0.5, "abs_tolerance": 1e-9})
        self.assertTrue(judge_answer(item, "1/2").correct)
        self.assertTrue(judge_answer(item, "$0.5$").correct)

    def test_integer_is_exact_and_rejects_prose(self):
        item = problem({"kind": "integer", "value": -3})
        self.assertTrue(judge_answer(item, r"\(-3\)").correct)
        result = judge_answer(item, "the answer is -3")
        self.assertFalse(result.correct)
        self.assertEqual(result.error, "parse_failure")

    def test_boolean_uses_configured_aliases(self):
        yes = problem(
            {"kind": "boolean", "value": True, "accepted_text": ["true", "yes"]}
        )
        self.assertTrue(judge_answer(yes, " YES ").correct)
        self.assertFalse(judge_answer(yes, "no").correct)

    def test_normalized_text_applies_declared_operations(self):
        item = problem(
            {
                "kind": "normalized_text",
                "accepted": ["lifo"],
                "normalization": [
                    "trim",
                    "unicode_nfkc",
                    "casefold",
                    "remove_math_delimiters",
                    "collapse_whitespace",
                ],
            }
        )
        self.assertTrue(judge_answer(item, " LIFO ").correct)

    def test_malformed_or_zero_denominator_fraction_is_incorrect(self):
        item = problem({"kind": "numeric", "value": 0.5, "abs_tolerance": 1e-9})
        for submitted in ("1//2", "1/0", "1/two"):
            with self.subTest(submitted=submitted):
                result = judge_answer(item, submitted)
                self.assertFalse(result.correct)
                self.assertEqual(result.error, "parse_failure")

    def test_arbitrary_expression_is_never_executed(self):
        item = problem({"kind": "numeric", "value": 2, "abs_tolerance": 0})
        result = judge_answer(item, "__import__('os').system('echo unsafe')")
        self.assertFalse(result.correct)
        self.assertEqual(result.error, "parse_failure")


if __name__ == "__main__":
    unittest.main()
