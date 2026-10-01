from actions.services import (
    ClimatiqClient,
    CurrencyClient,
    DuffelClient,
    OSRMClient,
    great_circle_distance_km,
)


class DummyResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status
        self.ok = 200 <= status < 300
        self.text = str(payload)

    def json(self):
        return self._payload


def test_haversine_berlin_paris_is_reasonable():
    distance = great_circle_distance_km(52.52, 13.405, 48.8566, 2.3522)
    assert 850 < distance < 900


def test_currency_conversion_parsing(monkeypatch):
    monkeypatch.setattr(
        "actions.services.requests.get",
        lambda *args, **kwargs: DummyResponse({"base": "EUR", "quote": "USD", "rate": 1.2}),
    )
    result = CurrencyClient().convert(10, "EUR", "USD")
    assert result["amount"] == 12.0
    assert result["rate"] == 1.2


def test_duffel_location_resolution(monkeypatch):
    monkeypatch.setenv("DUFFEL_ACCESS_TOKEN", "duffel_test_example")
    payload = {
        "data": [
            {
                "name": "Berlin",
                "city_name": "Berlin",
                "iata_code": "BER",
                "iata_country_code": "DE",
                "type": "city",
                "latitude": None,
                "longitude": None,
                "airports": [{"latitude": 52.36, "longitude": 13.50}],
            }
        ]
    }
    monkeypatch.setattr(
        "actions.services.requests.get",
        lambda *args, **kwargs: DummyResponse(payload),
    )
    result = DuffelClient().resolve_location("Berlin")
    assert result["iata_code"] == "BER"
    assert result["latitude"] == 52.36


def test_duffel_offer_parsing(monkeypatch):
    monkeypatch.setenv("DUFFEL_ACCESS_TOKEN", "duffel_test_example")
    payload = {
        "data": {
            "offers": [
                {
                    "id": "off_1",
                    "total_amount": "58.95",
                    "total_currency": "EUR",
                    "live_mode": False,
                    "owner": {"name": "Duffel Airways"},
                    "slices": [
                        {
                            "duration": "PT1H43M",
                            "segments": [
                                {
                                    "marketing_carrier": {"name": "Duffel Airways"},
                                    "origin": {"iata_code": "BER", "latitude": 52.36, "longitude": 13.50},
                                    "destination": {"iata_code": "CDG", "latitude": 49.01, "longitude": 2.55},
                                }
                            ],
                        }
                    ],
                }
            ]
        }
    }
    monkeypatch.setattr(
        "actions.services.requests.post",
        lambda *args, **kwargs: DummyResponse(payload),
    )
    offer = DuffelClient().flight_offers("BER", "CDG", "2030-10-20", max_results=1)[0]
    assert offer["price"] == 58.95
    assert offer["currency"] == "EUR"
    assert offer["carrier"] == "Duffel Airways"
    assert offer["distance_km"] > 800
    assert "raw" not in offer


def test_climatiq_estimate_parsing(monkeypatch):
    monkeypatch.setenv("CLIMATIQ_API_KEY", "example")
    payload = {
        "co2e": 25.6607,
        "co2e_unit": "kg",
        "co2e_calculation_method": "ar5",
        "emission_factor": {"name": "Example rail factor"},
    }
    monkeypatch.setattr(
        "actions.services.requests.post",
        lambda *args, **kwargs: DummyResponse(payload),
    )
    result = ClimatiqClient().rail_emissions(1000)
    assert result["co2e_kg"] == 25.6607
    assert result["distance_km"] == 1000


def test_osrm_distance_parsing(monkeypatch):
    monkeypatch.setattr(
        "actions.services.requests.get",
        lambda *args, **kwargs: DummyResponse({"routes": [{"distance": 1052490.2}]}),
    )
    distance = OSRMClient().driving_distance_km(52.52, 13.405, 48.8566, 2.3522)
    assert round(distance, 2) == 1052.49


def test_ticketmaster_event_parsing(monkeypatch):
    from actions.services import TicketmasterClient
    monkeypatch.setenv("TICKETMASTER_API_KEY", "example")
    payload = {
        "_embedded": {
            "events": [{
                "name": "Example Cultural Event",
                "dates": {"start": {"localDate": "2030-10-20", "localTime": "19:30:00"}},
                "_embedded": {"venues": [{"name": "Example Venue"}]},
                "classifications": [{"segment": {"name": "Arts & Theatre"}}],
                "url": "https://example.test/event",
            }]
        }
    }
    monkeypatch.setattr("actions.services.requests.get", lambda *args, **kwargs: DummyResponse(payload))
    event = TicketmasterClient().search_events("Berlin", max_results=1)[0]
    assert event["name"] == "Example Cultural Event"
    assert event["venue"] == "Example Venue"
    assert event["category"] == "Arts & Theatre"
