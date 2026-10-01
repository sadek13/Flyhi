"""Validation helpers for FlyHi form slots."""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta
from difflib import SequenceMatcher
from typing import Optional, Tuple

from dateutil import parser as date_parser


def basic_location_check(value: object) -> Optional[str]:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value).strip())
    if len(re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]", text)) < 2:
        return None
    if re.fullmatch(r"[\d\W_]+", text):
        return None
    return text.title()


def parse_trip_date(value: object) -> Optional[date]:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value).strip().lower())
    today = date.today()

    aliases = {
        "today": today,
        "tomorrow": today + timedelta(days=1),
        "day after tomorrow": today + timedelta(days=2),
    }
    if text in aliases:
        return aliases[text]

    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except (ValueError, TypeError, OverflowError):
            pass

    try:
        parsed = date_parser.parse(text, dayfirst=True, fuzzy=True, default=datetime.combine(today, time()))
        return parsed.date()
    except (ValueError, TypeError, OverflowError):
        return None


def _looks_like_dollar_word(token: str) -> bool:
    token = re.sub(r"[^a-z]", "", token.lower())
    if not token:
        return False
    return max(
        SequenceMatcher(None, token, candidate).ratio()
        for candidate in ("dollar", "dollars", "usd")
    ) >= 0.68


def validate_usd_budget(value: object) -> Tuple[Optional[float], Optional[str]]:
    if value is None:
        return None, "invalid"

    text = str(value).strip().lower()
    if not text:
        return None, "invalid"

    other_currency_patterns = (
        r"€|\beur\b|\beuro(?:s)?\b",
        r"£|\bgbp\b|\bpounds?\b",
        r"\baed\b|\bdirhams?\b",
        r"\blbp\b|\blira\b|\bpounds?\s+lebanese\b",
    )
    if any(re.search(pattern, text) for pattern in other_currency_patterns):
        return None, "currency"

    number_match = re.search(r"[-+]?\d+(?:[.,]\d+)?", text)
    if not number_match:
        return None, "invalid"

    try:
        amount = float(number_match.group(0).replace(",", "."))
    except ValueError:
        return None, "invalid"

    if amount <= 0:
        return None, "non_positive"

    # If a currency-like word is present, require it to look like USD/dollar.
    words = re.findall(r"[a-z]+", text)
    currencyish = [w for w in words if len(w) >= 3 and not w in {"my", "budget", "is", "about", "around"}]
    known_non_currency = {"for", "trip", "travel", "please", "approximately", "approx"}
    currencyish = [w for w in currencyish if w not in known_non_currency]
    if currencyish and not any(_looks_like_dollar_word(w) for w in currencyish):
        # Bare numeric budgets are allowed because the form prompt already says USD.
        # Ordinary filler words are ignored; unknown currency words are rejected.
        suspicious = [w for w in currencyish if w not in {"dollar", "dollars", "usd"}]
        if suspicious:
            return None, "currency"

    return round(amount, 2), None


def normalize_preference(value: object) -> Optional[str]:
    if value is None:
        return None
    text = re.sub(r"[^a-z\s]", " ", str(value).lower())
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return None

    phrase_aliases = {
        "greenest": ("greenest", "green", "eco", "sustainable", "lowest carbon", "least carbon", "carbon", "emissions"),
        "cheapest": ("cheapest", "cheap", "lowest price", "least expensive", "budget", "price"),
        "balanced": ("balanced", "balance", "both", "middle", "mix", "compromise"),
    }

    for canonical, aliases in phrase_aliases.items():
        if any(alias in text for alias in aliases):
            return canonical

    compact = text.replace(" ", "")
    best_label = None
    best_score = 0.0
    for canonical, aliases in phrase_aliases.items():
        for alias in aliases:
            score = SequenceMatcher(None, compact, alias.replace(" ", "")).ratio()
            if score > best_score:
                best_score = score
                best_label = canonical

    return best_label if best_score >= 0.62 else None
