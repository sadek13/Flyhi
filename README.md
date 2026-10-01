# FlyHi v3 — Eco-Travel Advisor

FlyHi is a Rasa 3.6 conversational prototype for sustainable trip planning. It gathers origin, destination, dates, USD budget and a sustainability preference, then compares transport price/carbon trade-offs and supports accommodation, cultural events, offset guidance, error recovery and human handover.

## Implemented scope

- Adaptive multi-turn Rasa form with validation.
- Greenest, cheapest and balanced transport ranking.
- Duffel place resolution and flight test offers.
- Climatiq transport carbon estimates and relative Eco Score.
- OSRM road distance and Frankfurter FX conversion.
- Labelled prototype rail/car prices and accommodation fixtures.
- Ticketmaster cultural events.
- Carbon-offset guidance with links to external standards; FlyHi does not sell offsets or claim carbon neutrality.
- Three-stage fallback and human handover with current trip context.
- Browser UI with bot-driven quick replies, green/amber/red result cards and a visible handover indicator.
- Automated Python unit tests plus Rasa NLU/Core test files.

## Local setup

Requires Python 3.10, Rasa Open Source 3.6.21 and Rasa SDK 3.6.2.

```bash
cp .env.example .env
```

Add your own private `DUFFEL_ACCESS_TOKEN`, `CLIMATIQ_API_KEY` and `TICKETMASTER_API_KEY`. Never commit `.env`.

```bash
set -a
source .env
set +a
python -m py_compile actions/*.py
pytest -q
rasa data validate
rasa train
```

### Run the app

Terminal 1:
```bash
set -a; source .env; set +a
rasa run actions
```

Terminal 2:
```bash
rasa run --enable-api --cors "*" --port 5005
```

Terminal 3:
```bash
python -m http.server 8080 --directory web
```

Open `http://localhost:8080`.

## Final verification commands

Run these on the target Mac after the implementation is frozen:

```bash
rasa data validate
rasa train
rasa test nlu --nlu tests/nlu_test.yml
rasa test nlu --cross-validation
rasa test core --stories tests/test_stories.yml
pytest -q
```

Use only the resulting real metrics/screenshots in the report.

## Docker

Docker configuration is included for reproducibility:

```bash
docker compose up --build
```

Do not state that Docker deployment was verified unless this command completes successfully on the target machine. The assignment deployment section should document the process and any unresolved deployment limitation truthfully.

## Important transparency notes

- Duffel test data is sandbox data.
- Rail/car prices are non-bookable prototype estimates.
- Accommodation is prototype fixture data, not live availability or certification.
- Eco Score is relative to the compared options only.
- Ticketmaster event information may change.
- Manual location input is supported; GPS is not implemented.
