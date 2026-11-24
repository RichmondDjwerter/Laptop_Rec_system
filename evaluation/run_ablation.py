"""Check what the extra budget and gaming rules change in the ranking."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import main
from evaluation.run_evaluation import SCENARIOS


def top(results, key):
    row = max(results, key=lambda item: item[key])
    return row["laptop"].name, row["laptop"].price_chf, row[key]


def show(result):
    name, price, score = result
    return f"{name.replace('|', '/')} (CHF {price:.0f}, {score*100:.1f}/100)"


def compare(results):
    for row in results:
        row["budget_only"] = row["base_score"] * row["budget_factor"]
        row["gpu_only"] = row["base_score"] * row["gpu_factor"]
    return {key: top(results, key) for key in
            ("base_score", "budget_only", "gpu_only", "score")}


def make_report():
    laptops = main.load_laptops()
    lines = [
        "# Model component ablation — Fuzzy Laptop Advisor", "",
        "We wanted to see whether our two extra scoring rules actually change "
        "the recommendations. For each test, we used the same laptops and "
        "preferences and switched the rules on or off.", "",
        "- **Budget rule:** lowers the score for a very large budget overrun.",
        "- **Gaming rule:** lowers the score of a weak GPU when gaming performance matters.", "",
        "## 1. Everyday test situations", "",
        "| Scenario | First laptop with basic score | Did the full model change it? |",
        "|---|---|---|",
    ]
    for scenario in SCENARIOS:
        results = main.rank_laptops(laptops, scenario.preferences())
        if not results:
            continue
        scores = compare(results)
        basic = scores["base_score"][0]
        final = scores["score"][0]
        changed = "Yes" if basic != final else "No"
        lines.append(f"| {scenario.title} | {basic} | {changed} |")

    lines += [
        "", "In these six situations, the extra rules do not always change the "
        "top laptop. That is fine: a rule should matter when the relevant "
        "problem occurs, not in every search.", "",
        "## 2. Cases where the rules matter", "",
        "We also tried two more extreme preference settings: a very small budget "
        "with high performance demands, and a gaming setup that is sensitive "
        "to both price and GPU strength.", "",
    ]
    stress_tests = (
        ("Very small budget, high performance",
         main.Preferences(500, 80, 2.5,
                          {"Price": 1, "Performance": 5,
                           "Portability": 0, "Battery size": 0}, workload="gaming")),
        ("Gaming: price and GPU both matter",
         main.Preferences(500, 60, 2.5,
                          {"Price": 3, "Performance": 4,
                           "Portability": 0, "Battery size": 0}, workload="gaming")),
    )
    for title, preferences in stress_tests:
        results = main.rank_laptops(laptops, preferences)
        scores = compare(results)
        lines += [
            f"### {title}", "",
            f"- Basic fuzzy score: {show(scores['base_score'])}",
            f"- With budget rule only: {show(scores['budget_only'])}",
            f"- With gaming rule only: {show(scores['gpu_only'])}",
            f"- With both rules: {show(scores['score'])}", "",
        ]

    lines += [
        "## What we learned", "",
        "The basic weighted score can sometimes give too much credit to a "
        "powerful but extremely expensive laptop. The budget rule helps "
        "reduce this problem, while the GPU rule accounts for gaming needs. "
        "The rules can change the ranking, but that alone does not prove "
        "which laptop is the best purchase.", "",
        "`Final score = weighted fuzzy score × budget factor × gaming GPU factor`", "",
        "*These tests use demonstration prices and hardware indices. "
        "The rule settings are part of our prototype.*", "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    output = Path(__file__).with_name("ABLATION_RESULTS.md")
    output.write_text(make_report(), encoding="utf-8")
    print(f"Saved: {output.name}")
