"""External service clients used by FlyHi.

The clients are deliberately small and keep provider-specific response handling
outside of the Rasa actions.
"""

from __future__ import annotations

import math
import os
from typing import Any, Dict, List, Optional

import requests


class ExternalServiceError(RuntimeError):
    """Raised when an external provider cannot satisfy a request."""


def great_circle_distance_km(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    """Return great-circle distance using the Haversine formula."""

    earth_radius_km = 6371.0088
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad)
        * math.cos(lat2_rad)
        * math.sin(delta_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return earth_radius_km * c


def _place_coordinates(place: Optional[Dict[str, Any]]) -> Optional[tuple[float, float]]:
    if not place:
        return None
    lat = place.get("latitude")
    lon = place.get("longitude")
    if lat is None or lon is None:
        return None
    try:
        return float(lat), float(lon)
    except (TypeError, ValueError):
        return None


class DuffelClient:
    """Small wrapper around Duffel Places and Flight Offer Requests."""

    def __init__(self) -> None:
        self.access_token = os.getenv("DUFFEL_ACCESS_TOKEN", "").strip()
        self.base_url = os.getenv("DUFFEL_BASE_URL", "https://api.duffel.com").rstrip("/")

    @property
    def configured(self) -> bool:
        return bool(self.access_token)

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Duffel-Version": "v2",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def resolve_location(self, text: str) -> Optional[Dict[str, Any]]:
        if not self.configured:
            raise ExternalServiceError("Duffel access token is not configured.")

        response = requests.get(
            f"{self.base_url}/places/suggestions",
            params={"query": text},
            headers=self._headers(),
            timeout=20,
        )
        if not response.ok:
            raise ExternalServiceError(
                f"Duffel place search failed ({response.status_code}): {response.text[:300]}"
            )

        places = response.json().get("data") or []
        if not places:
            return None

        query = text.strip().lower()
        places.sort(
            key=lambda place: (
                str(place.get("city_name") or place.get("name") or "").lower() != query,
                place.get("type") != "city",
            )
        )
        place = places[0]

        latitude = place.get("latitude")
        longitude = place.get("longitude")
        airports = place.get("airports") or []
        if (latitude is None or longitude is None) and airports:
            latitude = airports[0].get("latitude")
            longitude = airports[0].get("longitude")

        return {
            "name": place.get("city_name") or place.get("name") or text,
            "iata_code": place.get("iata_code"),
            "type": place.get("type"),
            "country_code": place.get("iata_country_code"),
            "latitude": latitude,
            "longitude": longitude,
        }

    def flight_offers(
        self,
        origin_code: str,
        destination_code: str,
        departure_date: str,
        return_date: Optional[str] = None,
        max_results: int = 5,
    ) -> List[Dict[str, Any]]:
        if not self.configured:
            raise ExternalServiceError("Duffel access token is not configured.")

        slices: List[Dict[str, str]] = [
            {
                "origin": origin_code.upper(),
                "destination": destination_code.upper(),
                "departure_date": departure_date,
            }
        ]
        if return_date:
            slices.append(
                {
                    "origin": destination_code.upper(),
                    "destination": origin_code.upper(),
                    "departure_date": return_date,
                }
            )

        response = requests.post(
            f"{self.base_url}/air/offer_requests",
            params={"return_offers": "true"},
            headers=self._headers(),
            json={
                "data": {
                    "slices": slices,
                    "passengers": [{"type": "adult"}],
                    "cabin_class": "economy",
                }
            },
            timeout=30,
        )
        if not response.ok:
            raise ExternalServiceError(
                f"Duffel request failed ({response.status_code}): {response.text[:300]}"
            )

        offers = (response.json().get("data") or {}).get("offers") or []
        results: List[Dict[str, Any]] = []

        for offer in offers[:max_results]:
            offer_slices = offer.get("slices") or []
            carrier: Optional[str] = None
            first_origin: Optional[Dict[str, Any]] = None
            final_destination: Optional[Dict[str, Any]] = None
            total_distance = 0.0
            distance_segments = 0
            stops = 0
            durations: List[str] = []

            for slice_data in offer_slices:
                if slice_data.get("duration"):
                    durations.append(str(slice_data["duration"]))
                segments = slice_data.get("segments") or []
                stops += max(0, len(segments) - 1)

                for segment in segments:
                    if carrier is None:
                        carrier = (segment.get("marketing_carrier") or {}).get("name")
                    origin = segment.get("origin") or {}
                    destination = segment.get("destination") or {}
                    if first_origin is None:
                        first_origin = origin
                    final_destination = destination

                    origin_coords = _place_coordinates(origin)
                    destination_coords = _place_coordinates(destination)
                    if origin_coords and destination_coords:
                        total_distance += great_circle_distance_km(
                            origin_coords[0],
                            origin_coords[1],
                            destination_coords[0],
                            destination_coords[1],
                        )
                        distance_segments += 1

            amount = offer.get("total_amount")
            try:
                price = float(amount) if amount is not None else None
            except (TypeError, ValueError):
                price = None

            results.append(
                {
                    "id": offer.get("id"),
                    "mode": "air",
                    "provider": "Duffel",
                    "price": price,
                    "currency": offer.get("total_currency"),
                    "carrier": carrier or (offer.get("owner") or {}).get("name"),
                    "duration": " + ".join(durations) if durations else None,
                    "origin": first_origin,
                    "destination": final_destination,
                    "distance_km": round(total_distance, 2) if distance_segments else None,
                    "stops": stops,
                    "live_mode": bool(offer.get("live_mode")),
                }
            )

        return results


class CurrencyClient:
    """Convert supplier prices to USD using Frankfurter public reference rates."""

    def __init__(self) -> None:
        self.base_url = os.getenv(
            "FRANKFURTER_BASE_URL", "https://api.frankfurter.dev"
        ).rstrip("/")

    def convert(self, amount: float, from_currency: str, to_currency: str = "USD") -> Dict[str, Any]:
        source = from_currency.upper()
        target = to_currency.upper()
        if source == target:
            return {"amount": float(amount), "rate": 1.0, "provider": "identity"}

        response = requests.get(
            f"{self.base_url}/v2/rate/{source.lower()}/{target.lower()}",
            timeout=15,
        )
        if not response.ok:
            raise ExternalServiceError(
                f"Currency conversion failed ({response.status_code}): {response.text[:200]}"
            )
        data = response.json()
        try:
            rate = float(data["rate"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ExternalServiceError("Currency response did not contain a valid rate.") from exc

        return {
            "amount": round(float(amount) * rate, 2),
            "rate": rate,
            "provider": "Frankfurter",
        }


class OSRMClient:
    def __init__(self) -> None:
        self.base_url = os.getenv(
            "OSRM_BASE_URL", "https://router.project-osrm.org"
        ).rstrip("/")

    def driving_distance_km(
        self,
        origin_lat: float,
        origin_lon: float,
        destination_lat: float,
        destination_lon: float,
    ) -> float:
        url = (
            f"{self.base_url}/route/v1/driving/"
            f"{origin_lon},{origin_lat};{destination_lon},{destination_lat}"
        )
        response = requests.get(url, params={"overview": "false"}, timeout=20)
        if not response.ok:
            raise ExternalServiceError(f"OSRM request failed ({response.status_code}).")

        payload = response.json()
        routes = payload.get("routes") or []
        if not routes:
            raise ExternalServiceError("OSRM returned no driving route.")
        distance_m = routes[0].get("distance")
        if distance_m is None:
            raise ExternalServiceError("OSRM response did not contain distance.")
        return float(distance_m) / 1000.0


class ClimatiqClient:
    """Climatiq public-factor estimates used by the prototype."""

    RAIL_FACTOR_ID = "5e49b19a-3258-8acd-9cfb-0aee76804cbe"
    CAR_FACTOR_ID = "e66d7a3e-6ffd-4f91-8305-87b103d12207"
    AIR_SHORT_FACTOR_ID = "31bd7117-c45d-8cf2-b5b4-c148ae93d2a6"
    AIR_LONG_FACTOR_ID = "677bc10e-1c16-8120-bc0a-8370be5ba083"

    def __init__(self) -> None:
        self.api_key = os.getenv("CLIMATIQ_API_KEY", "").strip()
        self.base_url = os.getenv("CLIMATIQ_BASE_URL", "https://api.climatiq.io").rstrip("/")
        self.estimate_path = os.getenv("CLIMATIQ_ESTIMATE_PATH", "/estimate").strip() or "/estimate"

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _estimate_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.configured:
            raise ExternalServiceError("Climatiq API key is not configured.")

        paths = [self.estimate_path]
        if self.estimate_path != "/data/v1/estimate":
            paths.append("/data/v1/estimate")

        last_error = ""
        for path in paths:
            response = requests.post(
                f"{self.base_url}/{path.lstrip('/')}",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=20,
            )
            if response.ok:
                return response.json()
            last_error = f"({response.status_code}): {response.text[:300]}"
            if response.status_code != 404:
                break

        raise ExternalServiceError(f"Climatiq request failed {last_error}")

    def estimate(self, factor_id: str, distance_km: float, passengers: int = 1) -> Dict[str, Any]:
        data = self._estimate_request(
            {
                "emission_factor": {"id": factor_id},
                "parameters": {
                    "passengers": passengers,
                    "distance": distance_km,
                    "distance_unit": "km",
                },
            }
        )
        return {
            "co2e_kg": data.get("co2e"),
            "co2e_unit": data.get("co2e_unit"),
            "distance_km": distance_km,
            "method": data.get("co2e_calculation_method"),
            "provider": "Climatiq",
            "factor": data.get("emission_factor"),
        }

    def rail_emissions(self, distance_km: float, passengers: int = 1) -> Dict[str, Any]:
        return self.estimate(self.RAIL_FACTOR_ID, distance_km, passengers)

    def car_emissions(self, distance_km: float, passengers: int = 1) -> Dict[str, Any]:
        return self.estimate(self.CAR_FACTOR_ID, distance_km, passengers)

    def air_emissions(self, distance_km: float, passengers: int = 1) -> Dict[str, Any]:
        factor_id = self.AIR_SHORT_FACTOR_ID if distance_km < 3700 else self.AIR_LONG_FACTOR_ID
        return self.estimate(factor_id, distance_km, passengers)
    
class TicketmasterClient:
   

        def __init__(self) -> None:
            self.api_key = os.getenv("TICKETMASTER_API_KEY", "").strip()
            self.base_url = os.getenv(
                "TICKETMASTER_BASE_URL",
                "https://app.ticketmaster.com/discovery/v2",
            ).rstrip("/")

        @property
        def configured(self) -> bool:
            return bool(self.api_key)

        def search_events(
            self,
            city: str,
            start_date: Optional[str] = None,
            end_date: Optional[str] = None,
            max_results: int = 5,
        ) -> List[Dict[str, Any]]:
            if not self.configured:
                raise ExternalServiceError("Ticketmaster API key is not configured.")

            params: Dict[str, Any] = {
                "apikey": self.api_key,
                "city": city,
                "size": max_results,
                "sort": "date,asc",
            }

            if start_date:
                params["startDateTime"] = f"{start_date}T00:00:00Z"

            if end_date:
                params["endDateTime"] = f"{end_date}T23:59:59Z"

            response = requests.get(
                f"{self.base_url}/events.json",
                params=params,
                timeout=20,
            )

            if not response.ok:
                raise ExternalServiceError(
                    f"Ticketmaster event search failed "
                    f"({response.status_code}): {response.text[:300]}"
                )

            events = (response.json().get("_embedded") or {}).get("events") or []
            results: List[Dict[str, Any]] = []

            for event in events[:max_results]:
                dates = event.get("dates") or {}
                start = dates.get("start") or {}

                venue = None
                venues = (event.get("_embedded") or {}).get("venues") or []
                if venues:
                    venue = venues[0].get("name")

                classifications = event.get("classifications") or []
                category = None
                if classifications:
                    segment = classifications[0].get("segment") or {}
                    category = segment.get("name")

                results.append(
                    {
                        "name": event.get("name"),
                        "date": start.get("localDate"),
                        "time": start.get("localTime"),
                        "venue": venue,
                        "category": category,
                        "url": event.get("url"),
                        "provider": "Ticketmaster",
                    }
                )

            return results