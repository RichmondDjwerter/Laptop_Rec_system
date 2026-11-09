# Fuzzy Laptop Advisor

A local website prototype that ranks laptops using fuzzy set membership scores and a weighted average. It first enforces hard requirements (budget, operating system, and an optional compatibility keyword), then scores the remaining laptops against soft preferences. The page shows criterion scores and weighted contributions for each recommendation.

## Run

Requires Python 3.10 or newer. There are no third-party Python dependencies.

```bash
python3 main.py
```

The catalog is in `laptops.csv`. 

## Fuzzy model

Each soft criterion produces a membership degree in `[0, 1]`. Price is fully suitable at or below 75% of the budget and falls linearly to zero at the budget. Performance and battery life use linear ramps around the user's desired value. Portability reverses a linear ramp, so lighter laptops receive higher suitability. Weights are normalized, and the final score is:

`score = sum(membership × criterion_weight) / sum(criterion_weights)`

## Project structure

- `main.py` — membership functions, hard filtering, ranking, explanation, and local web server
- `laptops.csv` — editable example catalog
- `web/` — local website files
