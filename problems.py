from __future__ import annotations

import random
from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class Problem:
    id: str
    category: str
    hidden_difficulty: str
    question: str
    answer: str
    accepted_answers: tuple[str, ...]
    explanation: str


PROBLEMS: list[Problem] = [
    Problem(
        id="math_001",
        category="math",
        hidden_difficulty="easy",
        question="What is 18 percent of 250?",
        answer="45",
        accepted_answers=("45", "45.0"),
        explanation="18 percent of 250 is 0.18 * 250 = 45.",
    ),
    Problem(
        id="math_002",
        category="math",
        hidden_difficulty="medium",
        question="Solve for x: 3x + 7 = 31.",
        answer="8",
        accepted_answers=("8", "8.0"),
        explanation="3x = 24, so x = 8.",
    ),
    Problem(
        id="probability_001",
        category="probability",
        hidden_difficulty="medium",
        question="A jar has 5 red balls, 4 blue balls, and 3 green balls. Two balls are drawn without replacement. What is the probability both are red?",
        answer="5/33",
        accepted_answers=("5/33", "20/132"),
        explanation="P(red then red) = 5/12 * 4/11 = 20/132 = 5/33.",
    ),
    Problem(
        id="logic_001",
        category="logic",
        hidden_difficulty="easy",
        question="True or false: If all bloops are razzies and all razzies are lazzies, then all bloops are lazzies.",
        answer="true",
        accepted_answers=("true", "t", "yes"),
        explanation="The conclusion follows by transitivity.",
    ),
    Problem(
        id="cs_001",
        category="computer science",
        hidden_difficulty="medium",
        question="What is the time complexity of merge sort on n items? Answer in Big-O notation.",
        answer="O(n log n)",
        accepted_answers=("o(n log n)", "o(nlogn)", "o(n log(n))"),
        explanation="Merge sort splits the input recursively and merges each level in linear time.",
    ),
    Problem(
        id="algorithms_001",
        category="algorithms",
        hidden_difficulty="hard",
        question="A binary search over a sorted array of 1024 elements needs at most how many comparisons?",
        answer="11",
        accepted_answers=("11",),
        explanation="The worst case is floor(log2(1024)) + 1 = 11 comparisons.",
    ),
    Problem(
        id="physics_001",
        category="physics",
        hidden_difficulty="medium",
        question="A car accelerates from rest at 3 m/s^2 for 4 seconds. What final speed does it reach in m/s?",
        answer="12",
        accepted_answers=("12", "12 m/s", "12.0"),
        explanation="v = at = 3 * 4 = 12 m/s.",
    ),
    Problem(
        id="probability_002",
        category="probability",
        hidden_difficulty="hard",
        question="A fair coin is flipped 4 times. What is the probability of getting exactly 3 heads?",
        answer="1/4",
        accepted_answers=("1/4", "4/16", "0.25", "25%"),
        explanation="There are C(4,3) = 4 favorable outcomes out of 16.",
    ),
    Problem(
        id="logic_002",
        category="logic",
        hidden_difficulty="hard",
        question="A statement says: 'This statement is false.' Is it consistently true, consistently false, or paradoxical?",
        answer="paradoxical",
        accepted_answers=("paradoxical", "paradox", "neither"),
        explanation="If true then false, and if false then true, so it is paradoxical.",
    ),
    Problem(
        id="math_003",
        category="math",
        hidden_difficulty="very hard",
        question="How many positive divisors does 360 have?",
        answer="24",
        accepted_answers=("24",),
        explanation="360 = 2^3 * 3^2 * 5, so divisors = (3+1)(2+1)(1+1) = 24.",
    ),
    Problem(
        id="algorithms_002",
        category="algorithms",
        hidden_difficulty="very hard",
        question="In a complete graph with 6 vertices, how many undirected edges are there?",
        answer="15",
        accepted_answers=("15",),
        explanation="A complete graph has n(n-1)/2 edges, so 6*5/2 = 15.",
    ),
    Problem(
        id="physics_002",
        category="physics",
        hidden_difficulty="hard",
        question="A 2 kg object experiences a net force of 10 N. What is its acceleration in m/s^2?",
        answer="5",
        accepted_answers=("5", "5.0", "5 m/s^2"),
        explanation="F = ma, so a = F/m = 10/2 = 5 m/s^2.",
    ),
    Problem(
        id="math_004",
        category="math",
        hidden_difficulty="easy",
        question="What is 7 squared?",
        answer="49",
        accepted_answers=("49",),
        explanation="7 squared is 7 * 7 = 49.",
    ),
    Problem(
        id="math_005",
        category="math",
        hidden_difficulty="medium",
        question="A number is doubled and then increased by 9 to get 35. What is the number?",
        answer="13",
        accepted_answers=("13",),
        explanation="2x + 9 = 35, so 2x = 26 and x = 13.",
    ),
    Problem(
        id="physics_003",
        category="physics",
        hidden_difficulty="easy",
        question="What is the weight in newtons of a 3 kg object if g = 10 m/s^2?",
        answer="30",
        accepted_answers=("30", "30 n", "30.0"),
        explanation="Weight = mg = 3 * 10 = 30 N.",
    ),
    Problem(
        id="physics_004",
        category="physics",
        hidden_difficulty="medium",
        question="A wave has frequency 5 Hz and wavelength 2 m. What is its speed in m/s?",
        answer="10",
        accepted_answers=("10", "10 m/s", "10.0"),
        explanation="Wave speed v = f * wavelength = 5 * 2 = 10 m/s.",
    ),
    Problem(
        id="physics_005",
        category="physics",
        hidden_difficulty="hard",
        question="A 4 kg cart moving at 3 m/s has how much kinetic energy in joules?",
        answer="18",
        accepted_answers=("18", "18 j", "18.0"),
        explanation="Kinetic energy = 1/2 * m * v^2 = 0.5 * 4 * 9 = 18 J.",
    ),
    Problem(
        id="cs_002",
        category="computer science",
        hidden_difficulty="easy",
        question="In binary, what is decimal 5?",
        answer="101",
        accepted_answers=("101", "0b101"),
        explanation="5 = 4 + 1, so its binary representation is 101.",
    ),
    Problem(
        id="cs_003",
        category="computer science",
        hidden_difficulty="easy",
        question="True or false: A stack is usually last-in, first-out.",
        answer="true",
        accepted_answers=("true", "t", "yes"),
        explanation="A stack uses LIFO ordering.",
    ),
    Problem(
        id="cs_004",
        category="computer science",
        hidden_difficulty="medium",
        question="What data structure normally supports FIFO behavior: stack or queue?",
        answer="queue",
        accepted_answers=("queue", "a queue"),
        explanation="A queue is first-in, first-out.",
    ),
    Problem(
        id="cs_005",
        category="computer science",
        hidden_difficulty="very hard",
        question="A hash table has load factor 0.75 and 120 filled slots. How many total slots does it have?",
        answer="160",
        accepted_answers=("160",),
        explanation="Load factor = filled / total, so total = 120 / 0.75 = 160.",
    ),
    Problem(
        id="logic_003",
        category="logic",
        hidden_difficulty="easy",
        question="If exactly one of A and B is true, and A is false, is B true or false?",
        answer="true",
        accepted_answers=("true", "b is true"),
        explanation="Exactly one is true. Since A is false, B must be true.",
    ),
    Problem(
        id="logic_004",
        category="logic",
        hidden_difficulty="medium",
        question="If P implies Q, P is true, and Q implies R, is R true?",
        answer="true",
        accepted_answers=("true", "yes"),
        explanation="P implies Q and P is true, so Q is true. Q implies R, so R is true.",
    ),
    Problem(
        id="probability_003",
        category="probability",
        hidden_difficulty="easy",
        question="A fair six-sided die is rolled once. What is the probability of rolling a 6?",
        answer="1/6",
        accepted_answers=("1/6", "0.1666666667"),
        explanation="One side out of six is a 6.",
    ),
    Problem(
        id="probability_004",
        category="probability",
        hidden_difficulty="medium",
        question="Two fair coins are flipped. What is the probability of getting at least one head?",
        answer="3/4",
        accepted_answers=("3/4", "0.75", "75%"),
        explanation="Only TT has no heads, so 3 of 4 outcomes have at least one head.",
    ),
]


def normalize_answer(answer: str) -> str:
    return answer.strip().lower().replace(" ", "")


def _as_fraction(value: str) -> Fraction | None:
    try:
        cleaned = value.strip().lower().replace(" ", "")
        if cleaned.endswith("%"):
            return Fraction(cleaned[:-1]) / 100
        return Fraction(cleaned)
    except Exception:
        return None


def is_correct(problem: Problem, submitted_answer: str) -> bool:
    normalized = normalize_answer(submitted_answer)
    accepted = {normalize_answer(answer) for answer in problem.accepted_answers}
    if normalized in accepted:
        return True

    submitted_fraction = _as_fraction(submitted_answer)
    if submitted_fraction is None:
        return False

    return any(
        (expected := _as_fraction(answer)) is not None and submitted_fraction == expected
        for answer in problem.accepted_answers
    )


def seeded_problem_sequence(seed: int, rounds: int) -> list[Problem]:
    rng = random.Random(seed)
    pool = PROBLEMS.copy()
    sequence: list[Problem] = []
    while len(sequence) < rounds:
        rng.shuffle(pool)
        sequence.extend(pool)
    return sequence[:rounds]
