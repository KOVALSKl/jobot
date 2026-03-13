from __future__ import annotations

from bot.services.vacancy_filter import (
    DEFAULT_EXCLUDE_MODE,
    build_vacancy_text,
    find_exclusion,
    normalize_exclude_mode,
    parse_excluded_terms,
)


def _vacancy(name: str, requirement: str = "", responsibility: str = "") -> dict:
    return {
        "id": "vac-1",
        "name": name,
        "snippet": {
            "requirement": requirement,
            "responsibility": responsibility,
        },
    }


def test_normalize_exclude_mode_fallback_to_default_safe() -> None:
    assert normalize_exclude_mode(None) == DEFAULT_EXCLUDE_MODE
    assert normalize_exclude_mode("") == DEFAULT_EXCLUDE_MODE
    assert normalize_exclude_mode("unknown") == DEFAULT_EXCLUDE_MODE
    assert normalize_exclude_mode("partial_aggressive") == "partial_aggressive"


def test_parse_excluded_terms_normalizes_case_and_yo() -> None:
    terms = parse_excluded_terms("  C++,   Ёлка , , 1С ")
    assert terms == ["c++", "елка", "1с"]


def test_default_safe_does_not_match_single_char_inside_cplusplus() -> None:
    vacancy = _vacancy(name="Разработчик C++")
    decision = find_exclusion(
        vacancy=vacancy,
        excluded_terms=["c"],
        exclude_mode="default_safe",
    )
    assert decision.is_excluded is False


def test_default_safe_matches_cplusplus_term_exactly() -> None:
    vacancy = _vacancy(name="Разработчик C++")
    decision = find_exclusion(
        vacancy=vacancy,
        excluded_terms=["c++"],
        exclude_mode="default_safe",
    )
    assert decision.is_excluded is True
    assert decision.matched_term == "c++"


def test_partial_aggressive_matches_single_char_inside_cplusplus() -> None:
    vacancy = _vacancy(name="Разработчик C++")
    decision = find_exclusion(
        vacancy=vacancy,
        excluded_terms=["c"],
        exclude_mode="partial_aggressive",
    )
    assert decision.is_excluded is True
    assert decision.mode == "partial_aggressive"


def test_mode_parity_for_1c_term() -> None:
    vacancy = _vacancy(name="Программист 1С")
    safe_decision = find_exclusion(
        vacancy=vacancy,
        excluded_terms=["1с"],
        exclude_mode="default_safe",
    )
    partial_decision = find_exclusion(
        vacancy=vacancy,
        excluded_terms=["1с"],
        exclude_mode="partial_aggressive",
    )
    assert safe_decision.is_excluded is True
    assert partial_decision.is_excluded is True


def test_build_vacancy_text_handles_empty_snippet() -> None:
    vacancy = {"name": "Python разработчик", "snippet": None}
    text = build_vacancy_text(vacancy)
    assert text == "python разработчик"
