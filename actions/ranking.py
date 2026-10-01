"""Transparent transport ranking and relative Eco Score."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional


def _number(value: Any) -> Optional[float]:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _budget_status(option: Dict[str, Any], budget_usd: Optional[float]) -> str:
    price = _number(option.get("price_usd"))
    if budget_usd is None or price is None:
        return "unknown"
    return "within" if price <= float(budget_usd) else "over"


def _budget_priority(status: str) -> int:
    return {"within": 0, "unknown": 1, "over": 2}.get(status, 1)


def _normalise(value: Optional[float], low: Optional[float], high: Optional[float]) -> float:
    if value is None:
        return 1.0
    if low is None or high is None or high <= low:
        return 0.0
    return (value - low) / (high - low)


def rank_options(
    options: Iterable[Dict[str, Any]],
    preference: str,
    budget_usd: Optional[float] = None,
) -> List[Dict[str, Any]]:
    ranked = [dict(option) for option in options]
    preference = (preference or "balanced").lower()

    prices = [_number(o.get("price_usd")) for o in ranked]
    emissions = [_number(o.get("co2e_kg")) for o in ranked]
    known_prices = [v for v in prices if v is not None]
    known_emissions = [v for v in emissions if v is not None]
    min_price = min(known_prices) if known_prices else None
    max_price = max(known_prices) if known_prices else None
    min_emission = min(known_emissions) if known_emissions else None
    max_emission = max(known_emissions) if known_emissions else None

    for option in ranked:
        option["budget_status"] = _budget_status(option, budget_usd)
        price = _number(option.get("price_usd"))
        emission = _number(option.get("co2e_kg"))
        option["balanced_score"] = round(
            0.5 * _normalise(price, min_price, max_price)
            + 0.5 * _normalise(emission, min_emission, max_emission),
            6,
        )

    def common(option: Dict[str, Any]) -> tuple:
        return (_budget_priority(option.get("budget_status", "unknown")),)

    if preference == "greenest":
        ranked.sort(
            key=lambda o: common(o)
            + (
                _number(o.get("co2e_kg")) if _number(o.get("co2e_kg")) is not None else float("inf"),
                _number(o.get("price_usd")) if _number(o.get("price_usd")) is not None else float("inf"),
            )
        )
    elif preference == "cheapest":
        ranked.sort(
            key=lambda o: common(o)
            + (
                _number(o.get("price_usd")) if _number(o.get("price_usd")) is not None else float("inf"),
                _number(o.get("co2e_kg")) if _number(o.get("co2e_kg")) is not None else float("inf"),
            )
        )
    else:
        ranked.sort(
            key=lambda o: common(o)
            + (
                float(o.get("balanced_score", 1.0)),
                _number(o.get("co2e_kg")) if _number(o.get("co2e_kg")) is not None else float("inf"),
            )
        )

    return ranked


def eco_score(options: Iterable[Dict[str, Any]], option: Dict[str, Any]) -> Optional[int]:
    values = [_number(o.get("co2e_kg")) for o in options]
    emissions = [v for v in values if v is not None]
    current = _number(option.get("co2e_kg"))
    if current is None or not emissions:
        return None

    minimum = min(emissions)
    maximum = max(emissions)
    if maximum <= minimum:
        return 100

    score = 100.0 * (maximum - current) / (maximum - minimum)
    return max(0, min(100, int(round(score))))
