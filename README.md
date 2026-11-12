# Fuzzy Laptop Advisor

A local website prototype that ranks laptops using fuzzy set membership scores and a weighted average. It first enforces hard requirements (budget, operating system, and an optional compatibility keyword), then scores the remaining laptops against soft preferences. The page shows criterion scores and weighted contributions for each recommendation.

## Run

Requires Python 3.10 or newer. There are no third-party Python dependencies.

```bash
python3 main.py
```

Then visit http://127.0.0.1:8000 in your browser. Stop the server with Ctrl+C. To use the old terminal questionnaire, run `python3 main.py --cli`.

The catalog is in `laptops.csv`. Required columns are model/name, price, weight in kg, and operating system. The loader accepts common alternatives such as `Model Name`, `Price (Euros)`, `Weight (kg)`, and `OpSys`. When performance is absent, it creates a rough CPU/RAM/GPU spec index; this is labelled as an estimate in the interface. Euro prices are converted to CHF using a fixed ECB reference rate of 0.9143 (6 Nov 2026); update this constant or convert prices yourself when using a different catalog. The bundled catalog is illustrative; performance is a relative project scale, not a standardized benchmark.

The sidebar has two preference input modes: sliders and a local natural-language parser. It maps explicit amounts and everyday phrases to crisp values that users can inspect and adjust. For example, “cheap” maps to a CHF 1,000 budget, “relatively cheap” to CHF 1,400, “fast” to performance 85/100, and “Mac” or “MacBook” to macOS. These are transparent project rules, not learned language understanding; the parser runs locally and sends no request to an NLP provider. Criterion weights and hard filters sit outside the tabs, so they apply to both modes.

## Fuzzy model

Each soft criterion produces a membership degree in `[0, 1]`. Price is fully suitable at or below 75% of the budget and falls linearly to zero at the budget. Performance uses a linear ramp around the user's desired value. Portability reverses a linear ramp, so lighter laptops receive higher suitability. Weights are normalized and the final score is:

`score = sum(membership × criterion_weight) / sum(criterion_weights)`

This is an illustrative model for a course prototype. The membership breakpoints, sample scale, and aggregation rule should be validated with users, as the project brief notes.

## Project structure

- `main.py` — membership functions, hard filtering, ranking, explanation, and local web server
- `laptops.csv` — editable example catalog
- `web/` — local website files
