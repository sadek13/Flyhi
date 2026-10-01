# Report evidence map

## Permanent figure numbering

1. **Figure 1 — Main Conversation Flow of the Eco-Travel Advisor** — already reserved/completed.
2. **Figure 2 — FlyHi Webchat Interface** — take after browser UI is verified.
3. **Figure 3 — Example Adaptive Trip-Planning Conversation** — use a working follow-up such as `show cheapest instead` and `why this option`.
4. **Figure 4 — Sustainable Travel Recommendation Results** — use the successful API-powered recommendation/comparison screenshot; this replaces weaker demo evidence rather than creating a new figure number.
5. **Figure 5 — Error Recovery and Human Handover** — take only after the three-step fallback/handover test passes.
6. **Figure 6 — Eco-Travel Advisor System Architecture** — build from `docs/ARCHITECTURE.md` after final verification.
7. **Figure 7 — Intent Classification Confusion Matrix** — take only from the real `rasa test nlu` output.

## Permanent code-block numbering already used in the report workflow

1. NLU Training Examples — `data/nlu.yml`
2. NLU Pipeline Configuration — `config.yml`
3. Trip Information Slots — `domain.yml`
4. Adaptive Trip-Planning Form — `domain.yml`
5. Trip-Planning Form Rules — `data/rules.yml`
6. Start-Date Normalization and Validation — `actions/actions.py`
7. End-Date Validation — `actions/actions.py`
8. USD Budget Validation — `actions/actions.py`
9. Travel Preference Validation — `actions/actions.py`
10. Requested-Slot Isolation and Robust Form Validation — `domain.yml` + validation behavior

Do not renumber 1–10. If a new report code block is needed, start at Code Block 11 only after the final implementation is verified.

## Strong implementation evidence in this version

- Duffel place resolution and flight offer service layer
- Climatiq fixed-factor estimates
- OSRM road distance
- Frankfurter USD conversion
- budget-aware Greenest/Cheapest/Balanced ranking
- relative Eco Score transparency
- adaptive preference reranking
- explanation of recommendation
- labelled accommodation prototype
- fallback escalation and handover context
- browser Webchat using Rasa REST channel
