# External API notes

## Duffel

Used for Places Suggestions and Flight Offer Requests. The project is configured for a Duffel test token during development. Test-mode schedules and prices are sandbox data and must not be described as current bookable market data.

- Places: `GET https://api.duffel.com/places/suggestions`
- Offer requests: `POST https://api.duffel.com/air/offer_requests?return_offers=true`

## Climatiq

The current user's existing FlyHi environment successfully verified `/estimate`; the client also falls back to the documented `/data/v1/estimate` path if `/estimate` returns 404.

Selected public factor IDs:

- Rail: `5e49b19a-3258-8acd-9cfb-0aee76804cbe`
- Car: `e66d7a3e-6ffd-4f91-8305-87b103d12207`
- Air short-haul: `31bd7117-c45d-8cf2-b5b4-c148ae93d2a6`
- Air long-haul: `677bc10e-1c16-8120-bc0a-8370be5ba083`

Previously verified 1000 km values in the user's current project:

- Rail: 25.6607 kg CO2e
- Car: 147.0 kg CO2e
- Air short-haul: 182.87 kg CO2e

Important limitation: the selected factors do not all have identical lifecycle boundaries. The prototype should state this in the report rather than present the comparison as a perfectly harmonised lifecycle assessment.

## OSRM

Used for car road distance. Public demo server is suitable for assignment prototyping but is not a production SLA.

## Frankfurter

Used only to convert a returned supplier currency to USD for comparison with the user-entered USD budget. No API key is required. It uses reference-rate data rather than real-time trading prices.

## Prototype rail/car fares

The project uses `RAIL_USD_PER_KM` and `CAR_USD_PER_KM` only to make Cheapest and Balanced ranking demonstrable across all modes. These values are not live market fares and every chatbot output labels them as prototype estimates.
