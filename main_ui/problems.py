"""Fixed math problem bank and deterministic answer validation."""

from __future__ import annotations

import math
import re
from fractions import Fraction
from typing import Any


PROBLEMS: list[dict[str, Any]] = [
    # Easy
    {
        "id": "arith_001",
        "difficulty": "easy",
        "category": "arithmetic",
        "question": "What is 47 + 86?",
        "answer": "133",
        "explanation": "47 + 86 = 133.",
        "cheap_stub": "133",
        "perturbation_stubs": ["133", "133", "133"],
        "deep_stub": "133",
    },
    {
        "id": "percent_001",
        "difficulty": "easy",
        "category": "percentages",
        "question": "What is 15% of 240?",
        "answer": "36",
        "explanation": "0.15 * 240 = 36.",
        "cheap_stub": "36",
        "perturbation_stubs": ["36", "36", "24"],
        "deep_stub": "36",
    },
    {
        "id": "arith_002",
        "difficulty": "easy",
        "category": "arithmetic",
        "question": "A shirt costs $40. After a 25% discount, what is the sale price?",
        "answer": "30",
        "explanation": "25% of 40 is 10; 40 - 10 = 30.",
        "cheap_stub": "30",
        "perturbation_stubs": ["30", "10", "30"],
        "deep_stub": "30",
    },
    {
        "id": "arith_003",
        "difficulty": "easy",
        "category": "arithmetic",
        "question": "Compute 12 * 13.",
        "answer": "156",
        "explanation": "12 * 13 = 156.",
        "cheap_stub": "156",
        "perturbation_stubs": ["156", "156", "156"],
        "deep_stub": "156",
    },
    {
        "id": "percent_002",
        "difficulty": "easy",
        "category": "percentages",
        "question": "A score rises from 80 to 92. What is the percent increase?",
        "answer": "15",
        "explanation": "(12 / 80) * 100 = 15%.",
        "cheap_stub": "12",
        "perturbation_stubs": ["15", "12", "15"],
        "deep_stub": "15",
        "showcase": True,
    },
    # Medium
    {
        "id": "algebra_001",
        "difficulty": "medium",
        "category": "algebra",
        "question": "Solve for x: 3x - 7 = 14.",
        "answer": "7",
        "explanation": "3x = 21, so x = 7.",
        "cheap_stub": "7",
        "perturbation_stubs": ["7", "7", "21"],
        "deep_stub": "7",
    },
    {
        "id": "probability_001",
        "difficulty": "medium",
        "category": "probability",
        "question": (
            "A jar has 5 red balls, 4 blue balls, and 3 green balls. "
            "Two balls are drawn without replacement. What is the probability both are red?"
        ),
        "answer": "5/33",
        "explanation": "There are 12 balls. P(red then red) = 5/12 * 4/11 = 20/132 = 5/33.",
        "cheap_stub": "1/6",
        "perturbation_stubs": ["1/6", "5/33", "5/33", "1/6"],
        "deep_stub": "5/33",
        "showcase": True,
    },
    {
        "id": "algebra_002",
        "difficulty": "medium",
        "category": "algebra",
        "question": "If 2(x + 4) = 3x - 1, what is x?",
        "answer": "9",
        "explanation": "2x + 8 = 3x - 1 => 9 = x.",
        "cheap_stub": "9",
        "perturbation_stubs": ["9", "7", "9"],
        "deep_stub": "9",
    },
    {
        "id": "probability_002",
        "difficulty": "medium",
        "category": "probability",
        "question": (
            "A fair six-sided die is rolled twice. What is the probability the sum is 7?"
        ),
        "answer": "1/6",
        "explanation": "6 of 36 outcomes sum to 7: (1,6),(2,5),(3,4),(4,3),(5,2),(6,1).",
        "cheap_stub": "1/6",
        "perturbation_stubs": ["1/6", "1/6", "7/36"],
        "deep_stub": "1/6",
    },
    {
        "id": "algebra_003",
        "difficulty": "medium",
        "category": "algebra",
        "question": "The average of 4 numbers is 18. Three of them are 12, 20, and 16. What is the fourth?",
        "answer": "24",
        "explanation": "Sum is 72. 72 - 12 - 20 - 16 = 24.",
        "cheap_stub": "18",
        "perturbation_stubs": ["24", "18", "24"],
        "deep_stub": "24",
        "showcase": True,
    },
    # Hard
    {
        "id": "combo_001",
        "difficulty": "hard",
        "category": "combinatorics",
        "question": "How many ways can 5 people sit in a row if 2 particular people must sit together?",
        "answer": "48",
        "explanation": "Treat the pair as a block: 4! * 2 = 48.",
        "cheap_stub": "24",
        "perturbation_stubs": ["48", "24", "48", "120"],
        "deep_stub": "48",
        "showcase": True,
    },
    {
        "id": "combo_002",
        "difficulty": "hard",
        "category": "combinatorics",
        "question": "How many distinct 4-letter words can be formed from the letters of PAPER if repetition is not allowed?",
        "answer": "60",
        "explanation": "PAPER has letters P,A,P,E,R (5 letters, P repeated). Distinct 4-letter selections: cases with/without both P's. Total distinct permutations of 4 distinct positions from {P,A,E,R} with at most two P's: 4! + C(3,2)*4!/2! wait — standard: total = 4 * P(4,3) wait. Letters: P twice, A,E,R unique. Cases: (1) no repeated P: choose 4 of {P,A,E,R} but only 4 distinct types... Distinct letters {P,A,E,R}. 4-letter no extra P: 4! = 24. With both P's: choose 2 more from {A,E,R}: C(3,2)=3, arrangements 4!/2! = 12, total 36. Wait 24+36=60.",
        "cheap_stub": "120",
        "perturbation_stubs": ["60", "120", "60"],
        "deep_stub": "60",
        "showcase": True,
    },
    {
        "id": "word_001",
        "difficulty": "hard",
        "category": "word problem",
        "question": (
            "A train 120 m long passes a platform 180 m long in 15 seconds. "
            "What is the train's speed in m/s?"
        ),
        "answer": "20",
        "explanation": "Distance = 120 + 180 = 300 m in 15 s => 20 m/s.",
        "cheap_stub": "8",
        "perturbation_stubs": ["20", "8", "20"],
        "deep_stub": "20",
        "showcase": True,
    },
    {
        "id": "combo_003",
        "difficulty": "hard",
        "category": "combinatorics",
        "question": "In how many ways can a committee of 3 be chosen from 8 people?",
        "answer": "56",
        "explanation": "C(8,3) = 56.",
        "cheap_stub": "56",
        "perturbation_stubs": ["56", "336", "56"],
        "deep_stub": "56",
    },
    {
        "id": "word_002",
        "difficulty": "hard",
        "category": "word problem",
        "question": (
            "Pipe A fills a tank in 6 hours and pipe B fills it in 8 hours. "
            "How many hours do they take together to fill the tank?"
        ),
        "answer": "24/7",
        "explanation": "1/6 + 1/8 = 7/24, so time = 24/7 hours.",
        "cheap_stub": "7",
        "perturbation_stubs": ["24/7", "7", "3.43"],
        "deep_stub": "24/7",
        "showcase": True,
    },
]


PRIZE_BY_DIFFICULTY = {
    "easy": 10,
    "medium": 20,
    "hard": 35,
}


def demo_schedule(n_rounds: int = 10) -> list[dict[str, Any]]:
    """Curated order: mix difficulties and include showcase items."""
    by_id = {p["id"]: p for p in PROBLEMS}
    order = [
        "arith_001",
        "percent_002",
        "probability_001",
        "algebra_001",
        "algebra_003",
        "arith_002",
        "combo_001",
        "word_001",
        "probability_002",
        "word_002",
    ]
    picked = [by_id[i] for i in order if i in by_id]
    if n_rounds <= len(picked):
        return picked[:n_rounds]
    extras = [p for p in PROBLEMS if p["id"] not in order]
    return (picked + extras)[:n_rounds]


_NUM = re.compile(r"[-+]?\d*\.?\d+(?:/\d+)?")


def _extract_numeric(text: str) -> str | None:
    if text is None:
        return None
    cleaned = str(text).strip().lower()
    cleaned = cleaned.replace("%", "").replace("$", "").replace(",", "")
    cleaned = cleaned.replace("hours", "").replace("hour", "").replace("m/s", "")
    cleaned = cleaned.strip()
    if not cleaned:
        return None
    # Prefer an explicit fraction
    frac = re.search(r"[-+]?\d+\s*/\s*\d+", cleaned)
    if frac:
        return re.sub(r"\s+", "", frac.group(0))
    m = _NUM.search(cleaned)
    return m.group(0) if m else cleaned


def answers_equivalent(a: str, b: str, tol: float = 1e-6) -> bool:
    sa = _extract_numeric(a)
    sb = _extract_numeric(b)
    if sa is None or sb is None:
        return str(a).strip().lower() == str(b).strip().lower()
    try:
        fa = float(Fraction(sa))
        fb = float(Fraction(sb))
        if math.isclose(fa, fb, rel_tol=0, abs_tol=tol):
            return True
        # percent-style: 15 vs 0.15
        if math.isclose(fa, fb * 100, abs_tol=1e-3) or math.isclose(fb, fa * 100, abs_tol=1e-3):
            return True
    except (ValueError, ZeroDivisionError):
        return sa.replace(" ", "") == sb.replace(" ", "")
    return False


def is_correct(given: str, problem: dict[str, Any]) -> bool:
    return answers_equivalent(given, problem["answer"])
