"""Доменная фильтрация вакансий по исключаемым терминам."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

ExcludeMode = Literal["default_safe", "partial_aggressive"]
DEFAULT_EXCLUDE_MODE: ExcludeMode = "default_safe"
_VALID_EXCLUDE_MODES = {"default_safe", "partial_aggressive"}


@dataclass(frozen=True)
class FilterDecision:
    """Результат проверки вакансии на исключение."""

    is_excluded: bool
    mode: ExcludeMode
    reason: str | None = None
    matched_term: str | None = None
    term_len_bucket: str | None = None


def normalize_exclude_mode(mode: str | None) -> ExcludeMode:
    """Нормализует входной режим фильтрации с fail-safe fallback."""
    candidate = (mode or "").strip().lower()
    if candidate in _VALID_EXCLUDE_MODES:
        return candidate  # type: ignore[return-value]
    return DEFAULT_EXCLUDE_MODE


def parse_excluded_terms(terms: str | None) -> list[str]:
    """Парсит CSV-строку исключаемых терминов в нормализованный список."""
    if not terms:
        return []
    result: list[str] = []
    for raw in terms.split(","):
        normalized = normalize_text(raw)
        if normalized:
            result.append(normalized)
    return result


def normalize_text(value: str | None) -> str:
    """Нормализует текст для предсказуемого сравнения."""
    if not value:
        return ""
    lowered = value.lower().replace("ё", "е")
    return " ".join(lowered.split())


def build_vacancy_text(vacancy: dict) -> str:
    """Собирает и нормализует текст вакансии для matching."""
    snippet = vacancy.get("snippet") or {}
    return normalize_text(
        " ".join(
            [
                vacancy.get("name") or "",
                snippet.get("requirement") or "",
                snippet.get("responsibility") or "",
            ]
        )
    )


def has_short_excluded_terms(terms: list[str], max_len: int = 1) -> bool:
    """Проверяет наличие коротких терминов, требующих UX-предупреждения."""
    return any(len(term) <= max_len for term in terms)


def find_exclusion(
    vacancy: dict,
    excluded_terms: list[str],
    exclude_mode: str | None = None,
) -> FilterDecision:
    """Возвращает решение фильтра по вакансии для выбранного режима."""
    mode = normalize_exclude_mode(exclude_mode)
    if not excluded_terms:
        return FilterDecision(is_excluded=False, mode=mode)

    text = build_vacancy_text(vacancy)
    for term in excluded_terms:
        if not term:
            continue
        if mode == "partial_aggressive":
            matched = term in text
        else:
            matched = _matches_default_safe(text, term)
        if matched:
            return FilterDecision(
                is_excluded=True,
                mode=mode,
                reason="excluded_term_match",
                matched_term=term,
                term_len_bucket=_term_len_bucket(term),
            )

    return FilterDecision(is_excluded=False, mode=mode)


def _matches_default_safe(text: str, term: str) -> bool:
    if _is_word_phrase(term):
        escaped = re.escape(term).replace(r"\ ", r"\s+")
        pattern = rf"(?<![\w+#]){escaped}(?![\w+#])"
        return re.search(pattern, text) is not None

    pattern = rf"(?<!\w){re.escape(term)}(?!\w)"
    return re.search(pattern, text) is not None


def _is_word_phrase(term: str) -> bool:
    return all(chunk.isalnum() for chunk in term.split())


def _term_len_bucket(term: str) -> str:
    length = len(term)
    if length <= 1:
        return "len_1"
    if length == 2:
        return "len_2"
    if length <= 4:
        return "len_3_4"
    return "len_5_plus"
