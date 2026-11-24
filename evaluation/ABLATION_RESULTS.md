# Model component ablation — Fuzzy Laptop Advisor

We wanted to see whether our two extra scoring rules actually change the recommendations. For each test, we used the same laptops and preferences and switched the rules on or off.

- **Budget rule:** lowers the score for a very large budget overrun.
- **Gaming rule:** lowers the score of a weak GPU when gaming performance matters.

## 1. Everyday test situations

| Scenario | First laptop with basic score | Did the full model change it? |
|---|---|---|
| Gaming: performance matters | Xiaomi Redmi G Pro 2024 Gaming Laptop | No |
| Study and general work | Xiaomi Redmi G Pro 2024 Gaming Laptop | No |
| Travel: portability matters | LG Gram 17 2023 17Z90R-G.CH77A2 Laptop | No |
| Strict budget, flexible specs | Asus Vivobook 16X 2023 K3605ZF-MB541WS Laptop | No |
| Gaming on a budget | Xiaomi Redmi G Pro 2024 Gaming Laptop | No |
| Low-cost everyday laptop | MSI GF63 Thin 11SC-1298IN Gaming Laptop | No |

In these six situations, the extra rules do not always change the top laptop. That is fine: a rule should matter when the relevant problem occurs, not in every search.

## 2. Cases where the rules matter

We also tried two more extreme preference settings: a very small budget with high performance demands, and a gaming setup that is sensitive to both price and GPU strength.

### Very small budget, high performance

- Basic fuzzy score: Lenovo Legion 9i 83AG0044IN Laptop (CHF 4000, 80.9/100)
- With budget rule only: Gigabyte G5 MF-E2IN313SHLaptop (CHF 650, 36.4/100)
- With gaming rule only: Lenovo Legion 9i 83AG0044IN Laptop (CHF 4000, 80.9/100)
- With both rules: Xiaomi Redmi G Pro 2024 Gaming Laptop (CHF 910, 36.1/100)

### Gaming: price and GPU both matter

- Basic fuzzy score: Acer Aspire 7 A715-76G UN.QMYSI.002 Gaming Laptop (CHF 480, 56.5/100)
- With budget rule only: Acer Aspire 7 A715-76G UN.QMYSI.002 Gaming Laptop (CHF 480, 56.5/100)
- With gaming rule only: Lenovo Legion 9i 83AG0044IN Laptop (CHF 4000, 56.3/100)
- With both rules: Acer Aspire 7 A715-76G UN.QMYSI.002 Gaming Laptop (CHF 480, 48.8/100)

## What we learned

The basic weighted score can sometimes give too much credit to a powerful but extremely expensive laptop. The budget rule helps reduce this problem, while the GPU rule accounts for gaming needs. The rules can change the ranking, but that alone does not prove which laptop is the best purchase.

`Final score = weighted fuzzy score × budget factor × gaming GPU factor`

*These tests use demonstration prices and hardware indices. The rule settings are part of our prototype.*
