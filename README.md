# Fuzzy Laptop Advisor

A local website prototype that ranks laptops using fuzzy set membership scores and a weighted average. It first enforces hard requirements (budget, operating system, and an optional compatibility keyword), then scores the remaining laptops against soft preferences. The page shows criterion scores and weighted contributions for each recommendation.

## Run

Requires Python 3.10 or newer. There are no third-party Python dependencies.

```bash
python3 main.py
```

Then visit http://127.0.0.1:8000 in your browser. Stop the server with Ctrl+C. To use the old terminal questionnaire, run `python3 main.py --cli`.

The catalog is in `laptops.csv`. Required columns are model/name, price, weight in kg, and operating system. The loader accepts common alternatives such as `Model Name`, `Price (Euros)`, `Weight (kg)`, and `OpSys`. When performance is absent, it creates a rough CPU/RAM/GPU spec index; this is explicitly labelled as an estimate in the interface. When battery life is absent, it leaves the value unavailable and excludes battery from that laptop's score rather than inventing a value. Euro prices are converted to CHF using a fixed ECB reference rate of 0.9143 (6 Nov 2026); update this constant or convert prices yourself when using a different catalog. The bundled catalog is illustrative; performance is a relative project scale, not a standardized benchmark.

## Fuzzy model

Each soft criterion produces a membership degree in `[0, 1]`. Price is fully suitable at or below 75% of the budget and falls linearly to zero at the budget. Performance and battery life use linear ramps around the user's desired value. Portability reverses a linear ramp, so lighter laptops receive higher suitability. Weights are normalized and the final score is:

`score = sum(membership × criterion_weight) / sum(criterion_weights)`

This is an illustrative model for a course prototype. The membership breakpoints, sample scale, and aggregation rule should be validated with users, as the project brief notes.

## Project structure

- `main.py` — membership functions, hard filtering, ranking, explanation, and local web server
- `laptops.csv` — editable example catalog
- `web/` — local website files
