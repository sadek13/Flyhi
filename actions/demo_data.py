"""Clearly labelled prototype fixtures used when live services are unavailable."""

from typing import Any, Dict, List


def demo_transport_options() -> List[Dict[str, Any]]:
    return [
        {
            "id": "demo-rail",
            "mode": "rail",
            "provider": "FlyHi demo fixture",
            "price_usd": 95.0,
            "co2e_kg": 18.0,
            "price_source": "demo fixture",
        },
        {
            "id": "demo-air",
            "mode": "air",
            "provider": "FlyHi demo fixture",
            "price_usd": 72.0,
            "co2e_kg": 145.0,
            "price_source": "demo fixture",
        },
        {
            "id": "demo-car",
            "mode": "car",
            "provider": "FlyHi demo fixture",
            "price_usd": 110.0,
            "co2e_kg": 92.0,
            "price_source": "demo fixture",
        },
    ]


def demo_hotels() -> List[Dict[str, Any]]:
    return [
        {
            "name": "Green Roof City Hotel",
            "nightly_price_usd": 115.0,
            "eco_score": 88,
            "eco_features": ["renewable electricity", "linen reuse", "public-transport access"],
        },
        {
            "name": "Central Eco Hostel",
            "nightly_price_usd": 62.0,
            "eco_score": 81,
            "eco_features": ["shared rooms", "waste sorting", "bike access"],
        },
        {
            "name": "Riverside Stay",
            "nightly_price_usd": 92.0,
            "eco_score": 74,
            "eco_features": ["water-saving fixtures", "local breakfast", "recycling"],
        },
    ]
