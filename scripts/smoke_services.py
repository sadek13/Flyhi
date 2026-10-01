"""Manual live-service smoke test. Run only after loading .env."""

from datetime import date, timedelta

from actions.services import ClimatiqClient, DuffelClient, OSRMClient


def main() -> None:
    duffel = DuffelClient()
    climatiq = ClimatiqClient()
    osrm = OSRMClient()

    berlin = duffel.resolve_location("Berlin")
    paris = duffel.resolve_location("Paris")
    print("Berlin:", berlin)
    print("Paris:", paris)

    departure = (date.today() + timedelta(days=30)).isoformat()
    offers = duffel.flight_offers("BER", "PAR", departure, max_results=3)
    print("\nDuffel offers:")
    for offer in offers:
        print(offer["carrier"], offer["price"], offer["currency"], offer["distance_km"])

    print("\nClimatiq 1000 km checks:")
    print("Rail:", climatiq.rail_emissions(1000)["co2e_kg"])
    print("Car:", climatiq.car_emissions(1000)["co2e_kg"])
    print("Air:", climatiq.air_emissions(1000)["co2e_kg"])

    print("\nOSRM Berlin -> Paris city-centre reference check:")
    print(round(osrm.driving_distance_km(52.5200, 13.4050, 48.8566, 2.3522), 2), "km")


if __name__ == "__main__":
    main()
