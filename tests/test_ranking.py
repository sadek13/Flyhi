from actions.demo_data import demo_transport_options
from actions.ranking import eco_score, rank_options


def test_demo_preference_rankings():
    options = demo_transport_options()
    assert rank_options(options, "greenest", 500)[0]["mode"] == "rail"
    assert rank_options(options, "cheapest", 500)[0]["mode"] == "air"
    assert rank_options(options, "balanced", 500)[0]["mode"] == "rail"


def test_budget_priority_is_applied():
    options = demo_transport_options()
    # With an $80 budget, only air is inside the stated budget.
    assert rank_options(options, "greenest", 80)[0]["mode"] == "air"


def test_relative_eco_scores():
    options = demo_transport_options()
    by_mode = {o["mode"]: o for o in options}
    assert eco_score(options, by_mode["rail"]) == 100
    assert eco_score(options, by_mode["air"]) == 0
    assert eco_score(options, by_mode["car"]) == 42
