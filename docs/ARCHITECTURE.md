# FlyHi v3 Architecture

```mermaid
flowchart LR
    U[User] --> W[FlyHi Web UI / Rasa Shell]
    W --> N[Rasa NLU + Rule/TED policies]
    N --> F[Trip Planning Form]
    F --> V[Custom Validation]
    V --> A[Custom Actions]
    A --> D[Duffel Places + Flight Test Offers]
    A --> O[OSRM Road Distance]
    A --> C[Climatiq Carbon Estimates]
    A --> X[Frankfurter FX Rates]
    A --> T[Ticketmaster Cultural Events]
    A --> R[Ranking + Relative Eco Score]
    A --> S[Prototype Accommodation Fixtures]
    A --> P[Offset Guidance + External Standards]
    A --> H[Fallback + Human Handover Context]
    R --> W
    T --> W
    S --> W
    P --> W
    H --> W
```

## Boundaries

- Duffel is used for place resolution and flight offers. Test/sandbox data must not be described as live bookable fares.
- Climatiq provides transport carbon estimates. FlyHi's Eco Score is a relative comparison inside the current result set, not a certification.
- OSRM supplies road distance; Frankfurter supplies reference FX conversion.
- Ticketmaster supplies cultural event information and may change after retrieval.
- Rail/car prices and accommodation are explicitly labelled prototype estimates/fixtures.
- Offset guidance is educational. FlyHi does not sell offsets or claim that purchasing an offset makes a trip carbon-neutral.
- Manual location input is used by the trip form; GPS is not required for this prototype.
