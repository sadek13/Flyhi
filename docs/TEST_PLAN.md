# FlyHi final verification plan

Run these on the user's Mac with Python 3.10 / Rasa 3.6.21.

## 1. Static and unit checks

```bash
python -m py_compile actions/*.py
pytest -q tests/test_validators.py tests/test_ranking.py tests/test_services.py
rasa data validate
rasa train
```

## 2. Live services

Load `.env`, then:

```bash
set -a
source .env
set +a
python scripts/smoke_services.py
```

Expected reference checks from the already-tested current project include approximately 25.66 kg rail, 147.0 kg car, 182.87 kg short-haul air per 1000 km, and ~1052.49 km for the explicit Berlin-centre to Paris-centre OSRM reference route.

## 3. Full trip test

Run action server and shell in separate terminals. Test:

- `plan a trip`
- Berlin
- Paris
- valid future departure
- later return date
- `5000 dollars`
- `greenest`
- `compare options`
- `show cheapest instead`
- `why this option`
- `what is eco score`
- `show hotels`

### Screenshot checkpoint

**Figure 3 — Example Adaptive Trip-Planning Conversation**  
Filename: `Figure_3_Example_Adaptive_Trip_Planning_Conversation.png`

For the main comparison evidence:

**Figure 4 — Sustainable Travel Recommendation Results**  
Filename: `Figure_4_Sustainable_Travel_Recommendation_Results.png`

## 4. Fallback and human handover

After a completed trip, send three unrelated messages such as:

- `zorbax flying potato 928`
- `purple toaster galaxy`
- `banana quantum taxi`

Expected:

1. rephrase request
2. explicit supported commands
3. handover message + JSON context

This specifically verifies that the completed form is no longer capturing unrelated post-trip text as a budget/date/preference value.

### Screenshot checkpoint

**Figure 5 — Error Recovery and Human Handover**  
Filename: `Figure_5_Error_Recovery_and_Human_Handover.png`

## 5. Webchat

Terminal A: `rasa run actions`  
Terminal B: `rasa run --enable-api --cors "*" --port 5005`  
Terminal C: `python -m http.server 8080 --directory web`

Open `http://localhost:8080` and repeat a short successful conversation.

### Screenshot checkpoint

**Figure 2 — FlyHi Webchat Interface**  
Filename: `Figure_2_FlyHi_Webchat_Interface.png`

## 6. Formal evaluation

```bash
rasa test nlu --nlu tests/nlu_test.yml
rasa test core --stories tests/test_stories.yml
```

Record the real precision/recall/F1 values. Do not use training accuracy as formal evaluation.

### Screenshot checkpoint

**Figure 7 — Intent Classification Confusion Matrix**  
Filename: `Figure_7_Intent_Classification_Confusion_Matrix.png`

## 7. Docker

Copy `.env.example` to `.env`, add private keys, then:

```bash
docker compose up --build
```

Verify action server, Rasa API and Web UI. Docker has not been executed in the generated environment and must be verified locally before the report says deployment is reproducible.
