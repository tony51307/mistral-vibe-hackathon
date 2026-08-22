from __future__ import annotations

from decimal import Decimal, InvalidOperation
import re
import unicodedata
from typing import Any

from .models import JudgeResult


_INTEGER_RE = re.compile(r"[+-]?\d+")
_DECIMAL_RE = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")
_FRACTION_RE = re.compile(r"([+-]?\d+)\s*/\s*([+-]?\d+)")
_ASYMPTOTIC_RE = re.compile(r"(?:[oθ]|theta)\s*\(", re.IGNORECASE)
_ANSWER_PREFIX_RE = re.compile(
    r"^(?:the\s+)?(?:final\s+)?answer\s*(?:is|:)\s*",
    re.IGNORECASE,
)


def _remove_math_delimiters(text: str) -> str:
    pairs = (("$", "$"), (r"\(", r"\)"), (r"\[", r"\]"))
    stripped = text.strip()
    for left, right in pairs:
        if stripped.startswith(left) and stripped.endswith(right) and len(stripped) >= len(left) + len(right):
            return stripped[len(left) : -len(right)].strip()
    return stripped


def _base_normalize(submitted: str) -> str:
    return _remove_math_delimiters(unicodedata.normalize("NFKC", submitted).strip())


def _parse_decimal(text: str) -> Decimal:
    if _DECIMAL_RE.fullmatch(text):
        return Decimal(text)
    match = _FRACTION_RE.fullmatch(text)
    if not match:
        raise InvalidOperation
    numerator = Decimal(match.group(1))
    denominator = Decimal(match.group(2))
    if denominator == 0:
        raise InvalidOperation
    return numerator / denominator


def _json_scalar(value: Decimal) -> int | float:
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def _normalize_text(value: str, operations: list[str]) -> str:
    result = value
    for operation in operations:
        if operation == "trim":
            result = result.strip()
        elif operation == "unicode_nfkc":
            result = unicodedata.normalize("NFKC", result)
        elif operation == "casefold":
            result = result.casefold()
        elif operation == "remove_math_delimiters":
            result = _remove_math_delimiters(result)
        elif operation == "collapse_whitespace":
            result = " ".join(result.split())
        else:
            return result
    return result


def _looks_asymptotic(value: str) -> bool:
    return bool(_ASYMPTOTIC_RE.search(value))


def _canonical_asymptotic(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip().casefold()
    normalized = _remove_math_delimiters(normalized)
    if "=" in normalized:
        normalized = normalized.rsplit("=", 1)[1].strip()
    normalized = normalized.replace("θ", "theta")
    normalized = re.sub(r"\b(?:o|theta)\s*\(", "complexity(", normalized)
    normalized = normalized.replace(" ", "")
    return normalized


def _strip_answer_prefix(value: str) -> str:
    return _ANSWER_PREFIX_RE.sub("", value.strip())


def _leading_answer_clause(value: str) -> str:
    stripped = _strip_answer_prefix(value)
    return re.split(r"[,.;:\n]|\s+-\s+|\s+because\b", stripped, maxsplit=1, flags=re.IGNORECASE)[
        0
    ].strip()


def _normalized_text_matches_with_explanation(
    submitted: str,
    accepted: set[str],
    operations: list[str],
) -> bool:
    candidates = {_normalize_text(_strip_answer_prefix(submitted), operations)}
    candidates.add(_normalize_text(_leading_answer_clause(submitted), operations))
    return bool(candidates & accepted)


def judge_answer(problem: dict[str, Any], submitted: str) -> JudgeResult:
    validator = problem["answer"]["validator"]
    kind = validator["kind"]
    if not isinstance(submitted, str):
        return JudgeResult(False, None, kind, "submission_not_string")

    try:
        if kind == "integer":
            normalized = _base_normalize(submitted)
            if not _INTEGER_RE.fullmatch(normalized):
                raise ValueError("parse_failure")
            parsed = int(normalized, 10)
            return JudgeResult(parsed == validator["value"], parsed, kind)

        if kind == "numeric":
            parsed_decimal = _parse_decimal(_base_normalize(submitted))
            expected = Decimal(str(validator["value"]))
            tolerance = Decimal(str(validator["abs_tolerance"]))
            correct = abs(parsed_decimal - expected) <= tolerance
            return JudgeResult(correct, _json_scalar(parsed_decimal), kind)

        if kind == "boolean":
            normalized = " ".join(unicodedata.normalize("NFKC", submitted).strip().casefold().split())
            aliases = {
                " ".join(unicodedata.normalize("NFKC", alias).strip().casefold().split())
                for alias in validator["accepted_text"]
            }
            leading = " ".join(
                unicodedata.normalize("NFKC", _leading_answer_clause(submitted))
                .strip()
                .casefold()
                .split()
            )
            if normalized not in aliases and leading not in aliases:
                raise ValueError("parse_failure")
            return JudgeResult(True, validator["value"], kind)

        if kind == "normalized_text":
            operations = validator["normalization"]
            normalized = _normalize_text(submitted, operations)
            accepted = {_normalize_text(value, operations) for value in validator["accepted"]}
            if normalized in accepted:
                return JudgeResult(True, normalized, kind)
            if _normalized_text_matches_with_explanation(submitted, accepted, operations):
                return JudgeResult(True, normalized, kind)
            if any(_looks_asymptotic(value) for value in accepted):
                canonical = _canonical_asymptotic(normalized)
                canonical_accepted = {_canonical_asymptotic(value) for value in accepted}
                return JudgeResult(canonical in canonical_accepted, normalized, kind)
            return JudgeResult(False, normalized, kind)
    except (InvalidOperation, ValueError, OverflowError):
        return JudgeResult(False, None, kind, "parse_failure")

    return JudgeResult(False, None, str(kind), "unsupported_validator")
