"""Compare fuzzy recommendations with hard filters and check ranking stability."""

from dataclasses import dataclass
from pathlib import Path
from statistics import mean
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import main

FEATURES = ("Price", "Performance", "Portability", "Battery size")


@dataclass(frozen=True)
class Scenario:
    title: str
    budget: float
    target: float
    weight: float
    price_importance: int
    performance_importance: int
    portability_importance: int
    battery_importance: int
    workload: str = "general"
    os: str = "Any"
    strict: bool = False

    def preferences(self, **updates):
        values = {
            "budget_chf": self.budget,
            "min_performance": self.target,
            "max_weight_kg": self.weight,
            "weights": dict(zip(FEATURES, (
                self.price_importance, self.performance_importance,
                self.portability_importance, self.battery_importance,
            ))),
            "operating_system": self.os,
            "strict_budget": self.strict,
            "workload": self.workload,
        }
        values.update(updates)
        return main.Preferences(**values)


SCENARIOS = (
    Scenario("Gaming: performance matters", 1000, 85, 2.5, 2, 5, 1, 1, "gaming"),
    Scenario("Study and general work", 1000, 75, 2.5, 4, 4, 1, 1),
    Scenario("Travel: portability matters", 1200, 60, 1.4, 3, 3, 5, 3),
    Scenario("Strict budget, flexible specs", 850, 75, 2.0, 4, 4, 2, 1, strict=True),
    Scenario("Gaming on a budget", 900, 80, 2.2, 4, 5, 2, 1, "gaming"),
    Scenario("Low-cost everyday laptop", 700, 55, 2.2, 5, 3, 2, 1),
)


def crisp_baseline(laptops, prefs):
    """Apply hard price, performance and weight limits to the same eligible laptops."""
    ranked = main.rank_laptops(laptops, prefs)
    return [row for row in ranked
            if row["laptop"].price_chf <= prefs.budget_chf
            and row["performance_index"] >= prefs.min_performance
            and row["laptop"].weight_kg <= prefs.max_weight_kg]


def top_names(results, n=5):
    return [row["laptop"].name for row in results[:n]]


def jaccard(a, b):
    first, second = set(a), set(b)
    return len(first & second) / len(first | second) if first or second else 1.0


def sensitivity(laptops, scenario):
    """Change one user preference at a time and compare the top five."""
    base = main.rank_laptops(laptops, scenario.preferences())
    changes = [
        ("Budget -50 CHF", {"budget_chf": scenario.budget - 50}),
        ("Budget +50 CHF", {"budget_chf": scenario.budget + 50}),
        ("Performance -5", {"min_performance": scenario.target - 5}),
        ("Performance +5", {"min_performance": scenario.target + 5}),
        ("Weight -0.1 kg", {"max_weight_kg": scenario.weight - 0.1}),
        ("Weight +0.1 kg", {"max_weight_kg": scenario.weight + 0.1}),
    ]
    for criterion in FEATURES:
        weights = scenario.preferences().weights
        if weights[criterion] > 0:
            new_weights = dict(weights)
            new_weights[criterion] -= 1
            if sum(new_weights.values()) > 0:
                changes.append((f"{criterion} importance -1", {"weights": new_weights}))
        if weights[criterion] < 5:
            new_weights = dict(weights)
            new_weights[criterion] += 1
            changes.append((f"{criterion} importance +1", {"weights": new_weights}))

    results = []
    for label, changed_values in changes:
        new_rank = main.rank_laptops(laptops, scenario.preferences(**changed_values))
        winner_changed = bool(base and new_rank and
                              base[0]["laptop"].name != new_rank[0]["laptop"].name)
        results.append((label, winner_changed,
                        jaccard(top_names(base), top_names(new_rank))))
    return results


def pareto_violations(laptops, scenario):
    """A laptop that is better on every checked field should not score worse."""
    ranked = main.rank_laptops(laptops, scenario.preferences())
    scores = {row["laptop"]: row["score"] for row in ranked}
    checked = 0
    issues = []
    for a in laptops:
        for b in laptops:
            if a is b or a.operating_system != b.operating_system:
                continue
            no_worse = (
                a.price_chf <= b.price_chf,
                a.weight_kg <= b.weight_kg,
                a.cpu_index >= b.cpu_index,
                a.gpu_index >= b.gpu_index,
                a.ram_gb >= b.ram_gb,
                a.battery_wh >= b.battery_wh,
            )
            better = (
                a.price_chf < b.price_chf,
                a.weight_kg < b.weight_kg,
                a.cpu_index > b.cpu_index,
                a.gpu_index > b.gpu_index,
                a.ram_gb > b.ram_gb,
                a.battery_wh > b.battery_wh,
            )
            if all(no_worse) and any(better) and a in scores and b in scores:
                checked += 1
                if scores[a] + 1e-10 < scores[b]:
                    issues.append((a.name, b.name, scores[a], scores[b]))
    return checked, issues


def build_report(laptops):
    lines = [
        "# Technical evaluation — Fuzzy Laptop Advisor", "",
        "We tested our laptop ranking on six example situations using the same "
        "catalog of demo laptops.", "",
        "## 1. Fuzzy ranking vs. hard filters", "",
        "Hard filters remove a laptop as soon as it misses a preferred budget, "
        "performance or weight limit. Our fuzzy model instead scores near matches. "
        "The strict-budget setting is still a hard limit.", "",
        "| Scenario | Hard filters: laptops left | Fuzzy: laptops ranked | First result (fit) |",
        "|---|---:|---:|---|",
    ]

    results_by_scenario = []
    for scenario in SCENARIOS:
        fuzzy = main.rank_laptops(laptops, scenario.preferences())
        hard = crisp_baseline(laptops, scenario.preferences())
        first = (f"{fuzzy[0]['laptop'].name} ({fuzzy[0]['score']*100:.1f}/100)"
                 if fuzzy else "No match")
        lines.append(f"| {scenario.title} | {len(hard)} | {len(fuzzy)} | {first} |")
        results_by_scenario.append((scenario, fuzzy))

    lines += [
        "", "**What we noticed:** hard filters sometimes return no laptops at all. "
        "Fuzzy ranking keeps the alternatives visible, but a low score still means "
        "a poor match.", "",
        "## 2. What happens when preferences change?", "",
        "We changed the budget by 50 CHF, the performance target by 5 points, "
        "the weight by 0.1 kg, and each importance setting by 1 point.", "",
        "| Scenario | Changes tested | Different first result | Top-5 overlap |",
        "|---|---:|---:|---:|",
    ]
    for scenario, _ in results_by_scenario:
        variants = sensitivity(laptops, scenario)
        flips = sum(changed for _, changed, _ in variants)
        overlap = mean(value for _, _, value in variants)
        lines.append(f"| {scenario.title} | {len(variants)} | {flips} | {overlap:.2f} |")

    lines += [
        "", "Top-5 overlap runs from 0 (no shared laptops) to 1 (the same five laptops). "
        "A change in first place is not necessarily a problem when scores are close.", "",
        "## 3. Basic checks", "",
    ]
    bad_scores = sum(not 0 <= row["score"] <= 1
                     for _, results in results_by_scenario for row in results)
    over_budget = sum(row["laptop"].price_chf > scenario.budget
                      for scenario, results in results_by_scenario if scenario.strict
                      for row in results)
    checked, problems = pareto_violations(laptops, SCENARIOS[0])
    lines += [
        f"- Scores stay between 0 and 100: **{'PASS' if not bad_scores else 'FAIL'}** "
        f"({bad_scores} issues).",
        f"- Strict budget is respected: **{'PASS' if not over_budget else 'FAIL'}** "
        f"({over_budget} issues).",
        f"- Better hardware at no higher price or weight should not score worse: "
        f"**{'PASS' if not problems else 'FAIL'}** "
        f"({checked} comparable pairs, {len(problems)} issues).", "",
        "## Summary", "",
        "The tests show that our ranking handles flexible preferences and basic "
        "constraints as expected in these examples. They do not tell us whether "
        "people will make better buying decisions.", "",
        "*The catalog prices and hardware scores are estimates, not current shop "
        "prices or measured benchmarks.*", "",
    ]
    return "\n".join(lines)


def main_cli():
    laptops = main.load_laptops()
    if main.LOAD_WARNINGS or not laptops:
        raise RuntimeError("The laptop catalog could not be loaded correctly.")
    output = Path(__file__).with_name("TECHNICAL_RESULTS.md")
    output.write_text(build_report(laptops), encoding="utf-8")
    print(f"Checked {len(laptops)} laptops in {len(SCENARIOS)} scenarios.")
    print(f"Saved: {output.name}")


if __name__ == "__main__":
    main_cli()
