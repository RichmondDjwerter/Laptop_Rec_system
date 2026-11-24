# Technical evaluation — Fuzzy Laptop Advisor

We tested our laptop ranking on six example situations using the same catalog of demo laptops.

## 1. Fuzzy ranking vs. hard filters

Hard filters remove a laptop as soon as it misses a preferred budget, performance or weight limit. Our fuzzy model instead scores near matches. The strict-budget setting is still a hard limit.

| Scenario | Hard filters: laptops left | Fuzzy: laptops ranked | First result (fit) |
|---|---:|---:|---|
| Gaming: performance matters | 0 | 56 | Xiaomi Redmi G Pro 2024 Gaming Laptop (76.0/100) |
| Study and general work | 1 | 56 | Xiaomi Redmi G Pro 2024 Gaming Laptop (83.7/100) |
| Travel: portability matters | 2 | 56 | LG Gram 17 2023 17Z90R-G.CH77A2 Laptop (78.5/100) |
| Strict budget, flexible specs | 0 | 23 | Asus Vivobook 16X 2023 K3605ZF-MB541WS Laptop (71.7/100) |
| Gaming on a budget | 0 | 56 | Xiaomi Redmi G Pro 2024 Gaming Laptop (72.3/100) |
| Low-cost everyday laptop | 4 | 56 | MSI GF63 Thin 11SC-1298IN Gaming Laptop (86.5/100) |

**What we noticed:** hard filters sometimes return no laptops at all. Fuzzy ranking keeps the alternatives visible, but a low score still means a poor match.

## 2. What happens when preferences change?

We changed the budget by 50 CHF, the performance target by 5 points, the weight by 0.1 kg, and each importance setting by 1 point.

| Scenario | Changes tested | Different first result | Top-5 overlap |
|---|---:|---:|---:|
| Gaming: performance matters | 13 | 0 | 0.79 |
| Study and general work | 14 | 1 | 0.98 |
| Travel: portability matters | 13 | 3 | 0.82 |
| Strict budget, flexible specs | 14 | 3 | 0.78 |
| Gaming on a budget | 13 | 5 | 0.92 |
| Low-cost everyday laptop | 13 | 4 | 1.00 |

Top-5 overlap runs from 0 (no shared laptops) to 1 (the same five laptops). A change in first place is not necessarily a problem when scores are close.

## 3. Basic checks

- Scores stay between 0 and 100: **PASS** (0 issues).
- Strict budget is respected: **PASS** (0 issues).
- Better hardware at no higher price or weight should not score worse: **PASS** (13 comparable pairs, 0 issues).

## Summary

The tests show that our ranking handles flexible preferences and basic constraints as expected in these examples. They do not tell us whether people will make better buying decisions.

*The catalog prices and hardware scores are estimates, not current shop prices or measured benchmarks.*
