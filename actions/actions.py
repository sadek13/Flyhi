"""FlyHi custom actions and form validation."""

from __future__ import annotations

import json
import os
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Text

from rasa_sdk import Action, Tracker
from rasa_sdk.events import AllSlotsReset, SlotSet
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.forms import FormValidationAction

from .demo_data import demo_hotels, demo_transport_options
from .ranking import eco_score, rank_options
from .services import (
    ClimatiqClient,
    CurrencyClient,
    DuffelClient,
    ExternalServiceError,
    OSRMClient,
    TicketmasterClient,
    great_circle_distance_km,
)
from .validators import (
    basic_location_check,
    normalize_preference,
    parse_trip_date,
    validate_usd_budget,
)


def _demo_mode() -> bool:
    return os.getenv("DEMO_MODE", "false").strip().lower() in {"1", "true", "yes", "on"}


def _nights(start_date: str, end_date: str) -> int:
    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()
    return max(1, (end - start).days)


def _coordinates(location: Dict[str, Any]) -> Optional[tuple[float, float]]:
    try:
        lat = location.get("latitude")
        lon = location.get("longitude")
        if lat is None or lon is None:
            return None
        return float(lat), float(lon)
    except (TypeError, ValueError):
        return None


def _prototype_price_usd(mode: str, distance_km: float) -> float:
    """Illustrative non-bookable price estimate for modes without a fare API."""
    default_rates = {"rail": 0.11, "car": 0.18}
    env_names = {"rail": "RAIL_USD_PER_KM", "car": "CAR_USD_PER_KM"}
    rate = float(os.getenv(env_names[mode], str(default_rates[mode])))
    return round(max(0.0, distance_km) * rate, 2)


def _recommendation_summary(
    option: Dict[str, Any],
    eco: Optional[int],
    budget: Optional[float] = None,
) -> str:
    parts = [str(option.get("mode", "option")).title()]

    if option.get("price_usd") is not None:
        price_source = option.get("price_source")
        label = f"${float(option['price_usd']):.2f}"
        if price_source == "prototype estimate":
            label += " estimated"
        parts.append(label)
    elif option.get("price") is not None:
        parts.append(f"{float(option['price']):.2f} {option.get('currency') or ''}".strip())
    else:
        parts.append("price unavailable")

    if option.get("co2e_kg") is not None:
        parts.append(f"{float(option['co2e_kg']):.1f} kg CO2e")
    else:
        parts.append("emissions unavailable")

    if eco is not None:
        parts.append(f"Eco Score {eco}/100")

    if budget is not None and option.get("price_usd") is not None:
        difference = float(option["price_usd"]) - float(budget)
        if difference <= 0:
            parts.append("within stated budget")
        else:
            parts.append(f"over budget by ${difference:.2f}")

    return " — ".join(parts)


def _load_recommendations(tracker: Tracker) -> Optional[Dict[str, Any]]:
    raw = tracker.get_slot("recommendation_json")
    if not raw:
        return None
    try:
        return json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, ValueError):
        return None


class ValidateTripPlanningForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_trip_planning_form"

    def validate_origin(self, slot_value, dispatcher, tracker, domain) -> Dict[Text, Any]:
        value = basic_location_check(slot_value)
        if not value:
            dispatcher.utter_message(
                text="Please enter a real place name with at least two letters, for example Berlin."
            )
            return {"origin": None}
        return {"origin": value}

    def validate_destination(self, slot_value, dispatcher, tracker, domain) -> Dict[Text, Any]:
        value = basic_location_check(slot_value)
        if not value:
            dispatcher.utter_message(
                text="Please enter a destination place name, for example Paris."
            )
            return {"destination": None}

        origin = str(tracker.get_slot("origin") or "").strip().lower()
        if origin and value.lower() == origin:
            dispatcher.utter_message(text="Your destination should be different from your origin.")
            return {"destination": None}
        return {"destination": value}

    def validate_start_date(self, slot_value, dispatcher, tracker, domain) -> Dict[Text, Any]:
        parsed = parse_trip_date(slot_value)
        if parsed is None:
            dispatcher.utter_message(
                text="I couldn't understand that date. Please use DD-MM-YYYY, YYYY-MM-DD, or say tomorrow."
            )
            return {"start_date": None}
        if parsed < date.today():
            dispatcher.utter_message(
                text="That date has already passed. Please enter a future departure date."
            )
            return {"start_date": None}
        return {"start_date": parsed.isoformat()}

    def validate_end_date(self, slot_value, dispatcher, tracker, domain) -> Dict[Text, Any]:
        parsed = parse_trip_date(slot_value)
        if parsed is None:
            dispatcher.utter_message(text="I couldn't understand that return date. Please enter a valid date.")
            return {"end_date": None}
        if parsed < date.today():
            dispatcher.utter_message(text="That return date has already passed. Please enter a future date.")
            return {"end_date": None}

        start_value = tracker.get_slot("start_date")
        if start_value:
            start = datetime.strptime(start_value, "%Y-%m-%d").date()
            if parsed <= start:
                dispatcher.utter_message(text="Your return date must be after your departure date.")
                return {"end_date": None}
        return {"end_date": parsed.isoformat()}

    def validate_budget(self, slot_value, dispatcher, tracker, domain) -> Dict[Text, Any]:
        amount, reason = validate_usd_budget(slot_value)
        if reason == "non_positive":
            dispatcher.utter_message(text="Your budget must be greater than zero.")
            return {"budget": None}
        if reason == "currency":
            dispatcher.utter_message(text="FlyHi currently accepts budgets in US dollars only.")
            return {"budget": None}
        if amount is None:
            dispatcher.utter_message(text="Please enter your budget in US dollars, for example 500 dollars.")
            return {"budget": None}
        return {"budget": amount}

    def validate_travel_preference(self, slot_value, dispatcher, tracker, domain) -> Dict[Text, Any]:
        preference = normalize_preference(slot_value)
        if preference is None:
            dispatcher.utter_message(text="Please choose greenest, balanced, or cheapest.")
            return {"travel_preference": None}
        return {"travel_preference": preference}


class ActionPlanTrip(Action):
    def name(self) -> Text:
        return "action_plan_trip"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        origin = tracker.get_slot("origin")
        destination = tracker.get_slot("destination")
        start_date = tracker.get_slot("start_date")
        end_date = tracker.get_slot("end_date")
        preference = tracker.get_slot("travel_preference") or "balanced"
        budget = tracker.get_slot("budget")

        if not all([origin, destination, start_date, end_date, budget]):
            dispatcher.utter_message(text="I am missing trip information. Please start the trip planner again.")
            return []

        if _demo_mode():
            options = demo_transport_options()
            ranked = rank_options(options, preference, budget)
            best = ranked[0]
            score = eco_score(options, best)
            dispatcher.utter_message(
                text=(
                    "DEMO MODE: these are labelled illustrative fixtures, not live prices or emissions. "
                    f"For your {preference} preference, the first demo option is "
                    f"{_recommendation_summary(best, score, budget)}."
                )
            )
            return [
                SlotSet("recommendation_json", json.dumps({"source": "demo", "options": ranked})),
                SlotSet("fallback_count", 0),
            ]

        duffel = DuffelClient()
        climatiq = ClimatiqClient()
        currency = CurrencyClient()
        osrm = OSRMClient()

        if not duffel.configured or not climatiq.configured:
            dispatcher.utter_message(response="utter_api_unavailable")
            dispatcher.utter_message(
                text="Configure DUFFEL_ACCESS_TOKEN and CLIMATIQ_API_KEY, or set DEMO_MODE=true."
            )
            return []

        try:
            origin_info = duffel.resolve_location(str(origin))
            destination_info = duffel.resolve_location(str(destination))
            if not origin_info or not origin_info.get("iata_code"):
                dispatcher.utter_message(text=f"I couldn't verify '{origin}' as a city or airport.")
                return [SlotSet("origin", None), SlotSet("origin_code", None)]
            if not destination_info or not destination_info.get("iata_code"):
                dispatcher.utter_message(text=f"I couldn't verify '{destination}' as a city or airport.")
                return [SlotSet("destination", None), SlotSet("destination_code", None)]

            origin_code = origin_info["iata_code"]
            destination_code = destination_info["iata_code"]
            origin_coords = _coordinates(origin_info)
            destination_coords = _coordinates(destination_info)
            if not origin_coords or not destination_coords:
                dispatcher.utter_message(text="I verified the cities but could not obtain route coordinates.")
                return [SlotSet("origin_code", origin_code), SlotSet("destination_code", destination_code)]

            direct_one_way_km = great_circle_distance_km(
                origin_coords[0], origin_coords[1], destination_coords[0], destination_coords[1]
            )
            direct_round_trip_km = direct_one_way_km * 2

            flights = duffel.flight_offers(
                origin_code=origin_code,
                destination_code=destination_code,
                departure_date=str(start_date),
                return_date=str(end_date),
                max_results=5,
            )
            options: List[Dict[str, Any]] = []
            fx_cache: Dict[str, Dict[str, Any]] = {}

            for flight in flights:
                option = dict(flight)
                flight_distance = float(option.get("distance_km") or direct_round_trip_km)
                air = climatiq.air_emissions(flight_distance, passengers=1)
                option["co2e_kg"] = round(float(air["co2e_kg"]), 2)
                option["distance_km"] = round(flight_distance, 2)
                option["emissions_source"] = "Climatiq"
                option["price_source"] = "Duffel test offer" if not option.get("live_mode") else "Duffel offer"

                price = option.get("price")
                code = str(option.get("currency") or "").upper()
                option["price_usd"] = None
                if price is not None and code:
                    try:
                        if code not in fx_cache:
                            fx_cache[code] = currency.convert(1.0, code, "USD")
                        option["fx_rate_to_usd"] = fx_cache[code]["rate"]
                        option["price_usd"] = round(float(price) * float(fx_cache[code]["rate"]), 2)
                        option["fx_provider"] = fx_cache[code]["provider"]
                    except ExternalServiceError:
                        pass
                options.append(option)

            rail = climatiq.rail_emissions(direct_round_trip_km, passengers=1)
            options.append(
                {
                    "id": "rail-route",
                    "mode": "rail",
                    "provider": "Climatiq + FlyHi prototype fare",
                    "price_usd": _prototype_price_usd("rail", direct_round_trip_km),
                    "price_source": "prototype estimate",
                    "distance_km": round(direct_round_trip_km, 2),
                    "distance_method": "great-circle approximation",
                    "co2e_kg": round(float(rail["co2e_kg"]), 2),
                    "emissions_source": "Climatiq",
                }
            )

            try:
                road_one_way_km = osrm.driving_distance_km(
                    origin_coords[0], origin_coords[1], destination_coords[0], destination_coords[1]
                )
                road_round_trip_km = road_one_way_km * 2
                car = climatiq.car_emissions(road_round_trip_km, passengers=1)
                options.append(
                    {
                        "id": "car-route",
                        "mode": "car",
                        "provider": "OSRM + Climatiq + FlyHi prototype fare",
                        "price_usd": _prototype_price_usd("car", road_round_trip_km),
                        "price_source": "prototype estimate",
                        "distance_km": round(road_round_trip_km, 2),
                        "distance_method": "OSRM road route",
                        "co2e_kg": round(float(car["co2e_kg"]), 2),
                        "emissions_source": "Climatiq",
                    }
                )
            except ExternalServiceError:
                pass

            if not options:
                dispatcher.utter_message(response="utter_api_unavailable")
                return [SlotSet("origin_code", origin_code), SlotSet("destination_code", destination_code)]

            ranked = rank_options(options, str(preference), float(budget))
            best = ranked[0]
            score = eco_score(options, best)
            sandbox = any(o.get("mode") == "air" and not o.get("live_mode", False) for o in options)

            text = (
                f"I found travel data for {origin_info['name']} to {destination_info['name']}. "
                f"For your {preference} preference, the first ranked option is "
                f"{_recommendation_summary(best, score, float(budget))}. "
                "Rail and car prices are clearly labelled prototype estimates; the Eco Score is relative to the options compared."
            )
            if sandbox:
                text += " Duffel is running in test mode, so flight schedules and fares are sandbox data."
            dispatcher.utter_message(text=text)
            dispatcher.utter_message(json_message={
                "result_cards": [
                    {
                        "rank": idx,
                        "mode": str(option.get("mode", "option")).title(),
                        "price_usd": option.get("price_usd"),
                        "co2e_kg": option.get("co2e_kg"),
                        "eco_score": eco_score(options, option),
                        "price_source": option.get("price_source"),
                    }
                    for idx, option in enumerate(ranked[:3], start=1)
                ],
                "quick_replies": [
                    {"title": "Compare options", "payload": "compare options"},
                    {"title": "Show hotels", "payload": "show accommodation"},
                    {"title": "Show activities", "payload": "show activities"},
                    {"title": "Carbon offsets", "payload": "show carbon offsets"},
                ],
            })

            return [
                SlotSet("origin", origin_info["name"]),
                SlotSet("destination", destination_info["name"]),
                SlotSet("origin_code", origin_code),
                SlotSet("destination_code", destination_code),
                SlotSet("recommendation_json", json.dumps({"source": "external", "options": ranked})),
                SlotSet("fallback_count", 0),
            ]

        except ExternalServiceError as exc:
            dispatcher.utter_message(response="utter_api_unavailable")
            dispatcher.utter_message(text=f"Technical detail: {exc}")
            return []


class ActionCompareOptions(Action):
    def name(self) -> Text:
        return "action_compare_options"

    def run(self, dispatcher, tracker, domain):
        payload = _load_recommendations(tracker)
        if not payload:
            dispatcher.utter_message(response="utter_no_recommendation")
            return []

        options = payload.get("options", [])[:3]
        all_options = payload.get("options", [])
        budget = tracker.get_slot("budget")
        lines = []
        for index, option in enumerate(options, start=1):
            score = eco_score(all_options, option)
            lines.append(f"{index}. {_recommendation_summary(option, score, budget)}")

        prefix = "DEMO FIXTURES:\n" if payload.get("source") == "demo" else "Top available options:\n"
        dispatcher.utter_message(text=prefix + "\n".join(lines))
        dispatcher.utter_message(json_message={
            "result_cards": [
                {
                    "rank": idx,
                    "mode": str(option.get("mode", "option")).title(),
                    "price_usd": option.get("price_usd"),
                    "co2e_kg": option.get("co2e_kg"),
                    "eco_score": eco_score(all_options, option),
                    "price_source": option.get("price_source"),
                }
                for idx, option in enumerate(options, start=1)
            ]
        })
        return [SlotSet("fallback_count", 0)]


class ActionChangePreference(Action):
    def name(self) -> Text:
        return "action_change_preference"

    def run(self, dispatcher, tracker, domain):
        preference = normalize_preference((tracker.latest_message or {}).get("text"))
        payload = _load_recommendations(tracker)
        if not preference:
            dispatcher.utter_message(text="Please say greenest, cheapest, or balanced.")
            return []
        if not payload or not payload.get("options"):
            dispatcher.utter_message(response="utter_no_recommendation")
            return [SlotSet("travel_preference", preference)]

        budget = tracker.get_slot("budget")
        reranked = rank_options(payload["options"], preference, budget)
        best = reranked[0]
        score = eco_score(reranked, best)
        dispatcher.utter_message(
            text=(
                f"I changed your preference to {preference}. The first option is now "
                f"{_recommendation_summary(best, score, budget)}."
            )
        )
        payload["options"] = reranked
        return [
            SlotSet("travel_preference", preference),
            SlotSet("recommendation_json", json.dumps(payload)),
            SlotSet("fallback_count", 0),
        ]


class ActionExplainRecommendation(Action):
    def name(self) -> Text:
        return "action_explain_recommendation"

    def run(self, dispatcher, tracker, domain):
        payload = _load_recommendations(tracker)
        if not payload or not payload.get("options"):
            dispatcher.utter_message(response="utter_no_recommendation")
            return []

        option = payload["options"][0]
        preference = tracker.get_slot("travel_preference") or "balanced"
        score = eco_score(payload["options"], option)
        reason = {
            "greenest": "it has the strongest emissions result among the currently ranked, budget-prioritised options",
            "cheapest": "it has the strongest comparable USD price result among the currently ranked, budget-prioritised options",
            "balanced": "it combines normalised price and emissions with equal weight after budget compatibility",
        }.get(str(preference), "it scored best under the current ranking settings")

        price_note = ""
        if option.get("price_source") == "prototype estimate":
            price_note = " Its price is a prototype estimate, not a bookable fare."
        elif option.get("price_source") == "Duffel test offer":
            price_note = " Its fare comes from Duffel test mode and is sandbox data."

        dispatcher.utter_message(
            text=(
                f"I ranked {str(option.get('mode', 'this option')).title()} first because {reason}. "
                f"Its current relative Eco Score is {score}/100. Eco Score is not an external certification; "
                f"it only compares the carbon estimates in this result set.{price_note}"
            )
        )
        return [SlotSet("fallback_count", 0)]


class ActionShowAccommodation(Action):
    def name(self) -> Text:
        return "action_show_accommodation"

    def run(self, dispatcher, tracker, domain):
        destination = tracker.get_slot("destination")
        start_date = tracker.get_slot("start_date")
        end_date = tracker.get_slot("end_date")
        preference = tracker.get_slot("travel_preference") or "balanced"

        if not destination:
            dispatcher.utter_message(text="Please complete a trip plan first so I know the destination.")
            return []

        hotels = [dict(h) for h in demo_hotels()]
        if preference == "greenest":
            hotels.sort(key=lambda h: (-h["eco_score"], h["nightly_price_usd"]))
        elif preference == "cheapest":
            hotels.sort(key=lambda h: (h["nightly_price_usd"], -h["eco_score"]))
        else:
            min_p = min(h["nightly_price_usd"] for h in hotels)
            max_p = max(h["nightly_price_usd"] for h in hotels)
            min_e = min(h["eco_score"] for h in hotels)
            max_e = max(h["eco_score"] for h in hotels)
            for hotel in hotels:
                p = (hotel["nightly_price_usd"] - min_p) / max(1.0, max_p - min_p)
                e = (max_e - hotel["eco_score"]) / max(1.0, max_e - min_e)
                hotel["balanced_score"] = 0.5 * p + 0.5 * e
            hotels.sort(key=lambda h: h["balanced_score"])

        nights = _nights(start_date, end_date) if start_date and end_date else None
        lines = []
        for idx, hotel in enumerate(hotels[:3], start=1):
            stay = f"; ${hotel['nightly_price_usd']:.0f}/night"
            if nights:
                stay += f", ${hotel['nightly_price_usd'] * nights:.0f} for {nights} nights"
            features = ", ".join(hotel["eco_features"][:2])
            lines.append(f"{idx}. {hotel['name']} — prototype Eco {hotel['eco_score']}/100{stay}; {features}")

        dispatcher.utter_message(
            text=(
                f"Prototype accommodation suggestions for {destination} ({preference}):\n"
                + "\n".join(lines)
                + "\nThese are labelled demo fixtures, not live availability, prices, or certified hotel sustainability ratings."
            )
        )
        return [SlotSet("fallback_count", 0)]

class ActionShowActivities(Action):
    def name(self) -> Text:
        return "action_show_activities"

    def run(self, dispatcher, tracker, domain):
        destination = tracker.get_slot("destination")
        start_date = tracker.get_slot("start_date")
        end_date = tracker.get_slot("end_date")

        if not destination:
            dispatcher.utter_message(
                text="Please complete a trip plan first so I know the destination."
            )
            return []

        client = TicketmasterClient()

        try:
            events = client.search_events(
                city=destination,
                start_date=start_date,
                end_date=end_date,
                max_results=3,
            )
        except ExternalServiceError as exc:
            dispatcher.utter_message(
                text=f"I could not retrieve activities right now. {exc}"
            )
            return [SlotSet("fallback_count", 0)]

        if not events:
            dispatcher.utter_message(
                text=f"I could not find Ticketmaster events for {destination} during your trip dates."
            )
            return [SlotSet("fallback_count", 0)]

        lines = []

        for idx, event in enumerate(events, start=1):
            event_date = event.get("date") or "date unavailable"
            event_time = event.get("time")
            venue = event.get("venue") or "venue unavailable"
            category = event.get("category") or "Event"

            when = event_date
            if event_time:
                when += f" at {event_time[:5]}"

            lines.append(
                f"{idx}. {event['name']} — {category}; "
                f"{when}; {venue}\n"
                f"{event['url']}"
            )

        dispatcher.utter_message(
            text=(
                f"Here are some activities and events in {destination} "
                f"from Ticketmaster:\n\n"
                + "\n\n".join(lines)
                + "\n\nEvent information comes from Ticketmaster and may change."
            )
        )

        return [SlotSet("fallback_count", 0)]

class ActionShowOffsets(Action):
    def name(self) -> Text:
        return "action_show_offsets"

    def run(self, dispatcher, tracker, domain):
        payload = _load_recommendations(tracker)
        if not payload:
            dispatcher.utter_message(
                text="Please plan a trip first so I can connect offset guidance to your travel emissions."
            )
            return []

        options = payload.get("options") or []
        best = options[0] if options else {}
        co2e = best.get("co2e_kg")
        amount = f"about {float(co2e):.1f} kg CO2e" if co2e is not None else "your remaining travel emissions"
        dispatcher.utter_message(
            text=(
                f"For the current first-ranked option, FlyHi estimates {amount}. "
                "Reducing emissions should come before offsetting. If you choose to offset residual emissions, "
                "look for projects with independent standards, public project documentation, additionality, "
                "and controls against double counting. FlyHi does not sell offsets or claim that an offset makes a trip carbon-neutral."
            )
        )
        dispatcher.utter_message(json_message={
            "offset_programs": [
                {"name": "Gold Standard", "url": "https://www.goldstandard.org/", "note": "Independent climate and sustainable-development standard."},
                {"name": "Verra VCS", "url": "https://verra.org/programs/verified-carbon-standard/", "note": "Verified Carbon Standard program; review individual project documentation before choosing."},
            ]
        })
        return [SlotSet("fallback_count", 0)]


class ActionFallbackHandler(Action):
    def name(self) -> Text:
        return "action_fallback_handler"

    def run(self, dispatcher, tracker, domain):
        count = int(tracker.get_slot("fallback_count") or 0) + 1
        if count == 1:
            dispatcher.utter_message(text="I didn't understand that. Please rephrase it in a short sentence.")
            return [SlotSet("fallback_count", count)]
        if count == 2:
            dispatcher.utter_message(
                text="I’m still not sure. You can say 'plan a trip', 'compare options', 'show hotels', 'show activities', 'show carbon offsets', 'why this option', 'cancel', or 'human advisor'."
            )
            return [SlotSet("fallback_count", count)]

        dispatcher.utter_message(
            text="I still can't understand the request, so I’ll prepare the current context for a human advisor instead of guessing."
        )
        slots = {
            key: tracker.get_slot(key)
            for key in ["origin", "destination", "start_date", "end_date", "budget", "travel_preference"]
            if tracker.get_slot(key) is not None
        }
        dispatcher.utter_message(json_message={"handover": True, "context": slots})
        return [SlotSet("fallback_count", 0), SlotSet("handover_requested", True)]


class ActionHumanHandover(Action):
    def name(self) -> Text:
        return "action_human_handover"

    def run(self, dispatcher, tracker, domain):
        slots = {
            key: tracker.get_slot(key)
            for key in ["origin", "destination", "start_date", "end_date", "budget", "travel_preference"]
            if tracker.get_slot(key) is not None
        }
        readable = ", ".join(f"{k.replace('_', ' ')}: {v}" for k, v in slots.items()) or "no trip details collected yet"
        dispatcher.utter_message(text=f"I'll prepare your current trip context for a human travel advisor: {readable}.")
        dispatcher.utter_message(json_message={"handover": True, "context": slots})
        return [SlotSet("handover_requested", True), SlotSet("fallback_count", 0)]


class ActionCancelTrip(Action):
    def name(self) -> Text:
        return "action_cancel_trip"

    def run(self, dispatcher, tracker, domain):
        dispatcher.utter_message(response="utter_cancelled")
        return [AllSlotsReset()]
