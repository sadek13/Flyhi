from datetime import date, timedelta

from actions.validators import (
    basic_location_check,
    normalize_preference,
    parse_trip_date,
    validate_usd_budget,
)


def test_location_validation():
    assert basic_location_check("berlin") == "Berlin"
    assert basic_location_check("new york") == "New York"
    assert basic_location_check("1") is None


def test_date_parsing_common_formats():
    future = date.today() + timedelta(days=30)
    assert parse_trip_date(future.strftime("%d-%m-%Y")) == future
    assert parse_trip_date(future.strftime("%d/%m/%Y")) == future
    assert parse_trip_date(future.isoformat()) == future
    assert parse_trip_date("tomorrow") == date.today() + timedelta(days=1)


def test_budget_accepts_usd_and_typos():
    assert validate_usd_budget("500 dollars") == (500.0, None)
    assert validate_usd_budget("600 dolars") == (600.0, None)
    assert validate_usd_budget("100 dolalrs") == (100.0, None)
    assert validate_usd_budget("$750") == (750.0, None)


def test_budget_rejects_other_currency_and_non_positive():
    assert validate_usd_budget("500 EUR")[1] == "currency"
    assert validate_usd_budget("-10 dollars")[1] == "non_positive"


def test_preference_normalisation_and_typos():
    assert normalize_preference("green") == "greenest"
    assert normalize_preference("cheap") == "cheapest"
    assert normalize_preference("balance") == "balanced"
    assert normalize_preference("blanac") == "balanced"
    assert normalize_preference("blanc") == "balanced"
    assert normalize_preference("show cheapest instead") == "cheapest"
    assert normalize_preference("purple helicopter") is None
