"""Fuzzy Laptop Advisor: a single-site, explainable fuzzy preference prototype."""

from __future__ import annotations

import csv
import io
import json
import math
import mimetypes
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from dataclasses import dataclass
from pathlib import Path


DATA_FILE = Path(__file__).with_name("laptops.csv")
LOAD_WARNINGS: list[str] = []


@dataclass(frozen=True)
class Laptop:
    name: str
    price_chf: float
    performance: float  # benchmark-style score, 0–100
    weight_kg: float
    operating_system: str
    compatibility: str
    cpu_model: str = ""
    gpu_model: str = ""
    ram_gb: int = 0
    storage_gb: int = 0
    battery_wh: float = 0.0
    cpu_index: float = 0.0
    gpu_index: float = 0.0


@dataclass(frozen=True)
class Preferences:
    budget_chf: float
    min_performance: float
    max_weight_kg: float
    weights: dict[str, float]
    operating_system: str = "Any"
    compatibility: str = "Any"
    strict_budget: bool = False
    workload: str = "general"


def ramp(value: float, low: float, high: float) -> float:
    """Linear fuzzy membership from 0 at low to 1 at high."""
    if high <= low:
        raise ValueError("high must be greater than low")
    return max(0.0, min(1.0, (value - low) / (high - low)))


def price_membership(price: float, budget: float) -> float:
    """Smooth affordable membership. Budget is preferred, not a hard cutoff.

    Value below 70% of budget: 1.0; at the preferred budget: 0.75;
    15% above: 0.35; 40% above: 0.0. Continuous across boundaries.
    These breakpoints are project assumptions to validate with users.
    """
    if budget <= 0:
        return 0.0
    x = price / budget
    if x <= 0.70:
        return 1.0
    if x <= 1.0:
        return 1.0 - (x - 0.70) * 0.25 / 0.30
    if x <= 1.15:
        return 0.75 - (x - 1.0) * 0.40 / 0.15
    if x <= 1.40:
        return 0.35 - (x - 1.15) * 0.35 / 0.25
    return 0.0


def performance_membership(value: float, target: float) -> float:
    """Continuous satisfaction of desired performance, with extra-performance bonus."""
    target = max(20.0, min(100.0, target))
    low, high = target * 0.60, min(target, 95.0)
    if value <= low:
        return 0.15 * max(value, 0) / low
    if value <= high:
        return 0.15 + 0.67 * (value - low) / (high - low)
    return min(1.0, 0.82 + 0.18 * (value - high) / (100 - high))


def portability_membership(weight: float, preferred_max: float) -> float:
    """Prefer lighter laptops, but allow slightly heavier ones."""
    good = preferred_max * 0.8
    if weight <= good:
        return 1.0
    if weight <= preferred_max:
        return 1.0 - (weight - good) * 0.20 / (preferred_max - good)
    return max(0.0, 0.80 - (weight - preferred_max) * 0.80 / (preferred_max * 0.50))


def battery_membership(capacity_wh: float) -> float:
    """Larger battery capacity proxy, NOT battery runtime in hours.

    A smooth type-1 membership function for 'large battery capacity'.
    The 35–95 Wh boundaries are illustrative project settings.
    """
    return ramp(capacity_wh, 35.0, 95.0)


def laptop_performance(laptop: Laptop, workload: str = "general") -> float:
    """0–100 transparent *illustrative* hardware index (NOT measured benchmarks).

    We separate CPU and GPU because graphics-heavy workloads value GPU more.
    Marketing labels, prices, battery and laptop category are never used here.
    """
    if not laptop.cpu_index or not laptop.gpu_index:
        return laptop.performance   # Allow tiny synthetic fixtures/legacy data.
    ram_index = min(100.0, 35.0 + 2.5 * laptop.ram_gb)
    if workload == "gaming":
        return .30 * laptop.cpu_index + .60 * laptop.gpu_index + .10 * ram_index
    return .62 * laptop.cpu_index + .23 * laptop.gpu_index + .15 * ram_index


def memberships(laptop: Laptop, prefs: Preferences) -> dict[str, float]:
    """Degree of preference satisfaction for each soft criterion, within [0,1]."""
    result = {
        "Price": price_membership(laptop.price_chf, prefs.budget_chf),
        "Performance": performance_membership(laptop_performance(laptop, prefs.workload), prefs.min_performance),
        "Portability": portability_membership(laptop.weight_kg, prefs.max_weight_kg),
    }
    if laptop.battery_wh > 0:
        result["Battery size"] = battery_membership(laptop.battery_wh)
    return result


def meets_constraints(laptop: Laptop, prefs: Preferences) -> bool:
    """Only genuinely mandatory constraints filter laptops out."""
    system = laptop.operating_system.casefold().replace(" ", "")
    wanted = prefs.operating_system.casefold().replace(" ", "")
    return (
        (not prefs.strict_budget or laptop.price_chf <= prefs.budget_chf)
        and (wanted == "any" or system == wanted)
        and (prefs.compatibility.casefold() == "any" or prefs.compatibility.casefold() in laptop.compatibility.casefold())
    )


def explain_match(laptop: Laptop, prefs: Preferences, scores: dict) -> str:
    """Two brief, understandable facts about the preference fit."""
    diff = laptop.price_chf - prefs.budget_chf
    if diff > 5:
        cost = f"CHF {diff:.0f} above your preferred budget"
    elif diff < -5:
        cost = f"CHF {-diff:.0f} below your preferred budget"
    else:
        cost = "close to your preferred budget"
    p = scores["Performance"]
    perf = "strong performance fit" if p >= .75 else "moderate performance fit" if p >= .45 else "performance below your preference"
    w = scores["Portability"]
    if w < .5 and prefs.weights.get("Portability", 0) > 0:
        portable = "; heavier than preferred"
    elif w >= .8 and prefs.weights.get("Portability", 0) > 0:
        portable = "; weight fits well"
    else:
        portable = ""
    return f"{cost}; {perf}{portable}."


def severe_overrun_factor(price: float, budget: float, price_weight: float) -> float:
    """Smooth protection against huge overspending on a *preferred* budget.

    No change up to +25%. Past this, score decays exponentially; no hard
    cutoff. Only applies when the user gives price nonzero importance.
    This is OUR prototype design choice, not a formula quoted from a textbook.
    """
    if price_weight <= 0 or budget <= 0 or price <= budget * 1.25:
        return 1.0
    relative_extra = price / budget - 1.25
    strength = 2.3 * min(1.0, price_weight / 2.0)
    from math import exp
    return exp(-strength * relative_extra)


def fuzzy_rule_cautions(laptop: Laptop, prefs: Preferences) -> dict[str, float]:
    """IF GPU is weak AND performance is important in games/3D THEN caution.

    Antecedents use Zadeh's min t-norm for fuzzy AND. The consequence
    is a *project-defined* continuous score adjustment, not Mamdani
    centroid defuzzification. We do not claim this is a full FIS.

    A second rule is explanation-only because very large budget overruns
    are already handled by severe_overrun_factor (avoid double penalties).
    """
    price_importance = max(0.0, min(1.0, prefs.weights.get("Price", 0) / 5.0))
    perf_importance = max(0.0, min(1.0, prefs.weights.get("Performance", 0) / 5.0))
    gpu_weak = 1.0 - ramp(laptop.gpu_index, 20.0, 70.0) if laptop.gpu_index > 0 else 0.0
    gaming_caution = min(perf_importance, gpu_weak) if prefs.workload == "gaming" else 0.0
    overrun = ramp(laptop.price_chf / prefs.budget_chf, 1.25, 1.75) if prefs.budget_chf > 0 else 0.0
    budget_caution = min(price_importance, overrun)
    return {"Gaming GPU caution": gaming_caution, "Budget overrun caution": budget_caution}


def rank_laptops(laptops: list[Laptop], prefs: Preferences) -> list[dict]:
    """Return sorted eligible laptops. Validate preferences, including API callers."""
    if not math.isfinite(prefs.budget_chf) or prefs.budget_chf <= 0:
        raise ValueError("Budget must be a positive finite number")
    if not math.isfinite(prefs.min_performance) or not 0 <= prefs.min_performance <= 100:
        raise ValueError("Desired performance must be between 0 and 100")
    if not math.isfinite(prefs.max_weight_kg) or prefs.max_weight_kg <= 0:
        raise ValueError("Preferred weight must be positive")
    if prefs.workload not in ("general", "gaming"):
        raise ValueError("Unknown main task")
    eligible = [laptop for laptop in laptops if meets_constraints(laptop, prefs)]
    total_weight = sum(prefs.weights.values())
    if total_weight <= 0 or any(not math.isfinite(weight) or weight < 0 or weight > 5 for weight in prefs.weights.values()):
        raise ValueError("Preference weights must be non-negative and have a positive total")

    results = []
    for laptop in eligible:
        scores = memberships(laptop, prefs)
        included_weight = sum(prefs.weights.get(key, 0) for key in scores)
        contributions = {key: scores[key] * prefs.weights.get(key, 0) / included_weight for key in scores} if included_weight else {}
        guard = severe_overrun_factor(laptop.price_chf, prefs.budget_chf, prefs.weights.get("Price", 0))
        rules = fuzzy_rule_cautions(laptop, prefs)
        # A modest, smooth non-compensatory safeguard for important gaming needs.
        # The price rule is already reflected in "guard", not applied a second time.
        gpu_factor = 1.0 - 0.18 * rules["Gaming GPU caution"]
        warnings = []
        if rules["Gaming GPU caution"] >= 0.35:
            warnings.append("Limited graphics power for demanding games or 3D tasks")
        if rules["Budget overrun caution"] >= 0.35:
            warnings.append("Noticeably above your preferred budget")
        results.append({
            "laptop": laptop,
            "performance_index": laptop_performance(laptop, prefs.workload),
            "base_score": sum(contributions.values()),
            "score": sum(contributions.values()) * guard * gpu_factor,
            "budget_factor": guard,
            "gpu_factor": gpu_factor,
            "rule_strengths": rules,
            "warnings": warnings,
            "memberships": scores,
            "contributions": contributions,
            "explanation": explain_match(laptop, prefs, scores),
        })
    return sorted(results, key=lambda item: item["score"], reverse=True)


def load_laptops(path: Path = DATA_FILE) -> list[Laptop]:
    LOAD_WARNINGS.clear()
    raw_csv = path.read_bytes()
    try:
        csv_text = raw_csv.decode("utf-8-sig")
    except UnicodeDecodeError:
        # Many exported laptop catalogs contain Windows-1252 characters such
        # as accented letters in product names or descriptions.
        csv_text = raw_csv.decode("cp1252")
    reader = csv.DictReader(io.StringIO(csv_text, newline=""))
    if not reader.fieldnames:
        raise ValueError("The laptop CSV is empty or has no header row.")
    aliases = {
        "name": ("name", "model", "model name", "product", "laptop", "brand model"),
        "price": ("price_chf", "price", "price chf", "price (chf)", "price_euros", "price euros", "price (euros)", "price ($)"),
        "performance": ("performance", "performance score", "performance (0-100)", "benchmark score"),
        "weight": ("weight_kg", "weight", "weight kg", "weight (kg)", "laptop weight"),
        "os": ("operating_system", "operating system", "os", "opsys"),
        "compatibility": ("compatibility", "special features", "features"),
    }
    headers = {header.strip().casefold(): header for header in reader.fieldnames if header}
    columns = {}
    for key, names in aliases.items():
        columns[key] = next((headers[name.casefold()] for name in names if name.casefold() in headers), None)
    required = [key for key in ("name", "price", "weight", "os") if not columns[key]]
    if required:
        pretty = {"name": "model/name", "price": "price", "weight": "weight in kg", "os": "operating system"}
        raise ValueError("CSV is missing required column(s): " + ", ".join(pretty[key] for key in required) + ".")
    currency_header = columns["price"].casefold()
    euro_price = "euro" in currency_header or "price_euros" in currency_header
    euro_to_chf = 0.9143  # ECB reference rate, 6 Nov 2026
    cpu_col = headers.get("cpu") or headers.get("processor")
    gpu_col = headers.get("gpu") or headers.get("graphics")
    ram_col = headers.get("ram") or headers.get("memory (ram)")
    laptops = []
    for row_number, row in enumerate(reader, start=2):
        try:
            raw_price = _number(row[columns["price"]])
            price_chf = raw_price * euro_to_chf if euro_price else raw_price
            performance = _number(row[columns["performance"]]) if columns["performance"] else _estimate_performance(
                row.get(cpu_col, "") if cpu_col else "", row.get(gpu_col, "") if gpu_col else "", row.get(ram_col, "") if ram_col else "")
            laptops.append(Laptop(
                name=(row[columns["name"]].strip() if columns["name"] else row.get("Manufacturer", "") + " " + row.get("Product", "")).strip(), price_chf=price_chf,
                performance=performance,
                weight_kg=float(str(row[columns["weight"]]).lower().replace("kgs", "").replace("kg", "").strip()),
                operating_system=row[columns["os"]].strip(),
                compatibility=row[columns["compatibility"]].strip() if columns["compatibility"] else "",
                cpu_model=row.get("cpu_model", "").strip(),
                gpu_model=row.get("gpu_model", "").strip(),
                ram_gb=int(float(row.get("ram_gb", "0") or "0")),
                storage_gb=int(float(row.get("storage_gb", "0") or "0")),
                battery_wh=float(row.get("battery_wh", "0") or "0"),
                cpu_index=float(row.get("cpu_index", "0") or "0"),
                gpu_index=float(row.get("gpu_index", "0") or "0"),
            ))
        except (ValueError, TypeError, KeyError) as exc:
            warning = f"Skipped CSV row {row_number}: {exc}"
            LOAD_WARNINGS.append(warning)
            print(warning, file=sys.stderr)
    return laptops


def _number(value: str) -> float:
    cleaned = str(value).strip().lower().replace("chf", "").replace("eur", "").replace("€", "").replace("$", "").replace("kg", "").replace("hours", "").replace("h", "").strip()
    if "," in cleaned and "." in cleaned:
        decimal_mark = "," if cleaned.rfind(",") > cleaned.rfind(".") else "."
        thousands_mark = "." if decimal_mark == "," else ","
        cleaned = cleaned.replace(thousands_mark, "").replace(decimal_mark, ".")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")
    return float(cleaned)


def _estimate_performance(cpu: str, gpu: str, ram: str) -> float:
    """Rough spec-based index for catalogs without measured benchmark scores."""
    text = cpu.casefold()
    import re
    tier = re.search(r"\b(?:core\s+)?i([3579])\b|\bryzen\s+([3579])\b|\bcore\s+ultra\s+([3579])\b|\bm([1-5])\b", text)
    score = 52.0
    if tier:
        digit = next(int(value) for value in tier.groups() if value)
        score = {1: 35, 2: 40, 3: 45, 4: 48, 5: 58, 6: 64, 7: 72, 8: 78, 9: 84}.get(digit, 52)
    ram_match = re.search(r"(\d+)\s*gb", ram.casefold())
    if ram_match:
        score += max(-10, min(10, (int(ram_match.group(1)) - 8) * 0.7))
    if any(token in gpu.casefold() for token in ("rtx", "gtx", "radeon rx", "geforce")):
        score += 10
    return max(20.0, min(100.0, score))


def interpret_request(text: str, defaults: dict | None = None) -> dict:
    """Map plain language into editable, crisp preference values (no external NLP service)."""
    lower = re.sub(r"\b(?:a|one)\s+grand\b", "1000", text.strip().casefold())
    values = {
        "budget": float((defaults or {}).get("budget", 1500)),
        "performance": float((defaults or {}).get("performance", 65)),
        "weight": float((defaults or {}).get("weight", 1.8)),
        "os": (defaults or {}).get("os", "Any"),
        "compatibility": (defaults or {}).get("compatibility", "Any"),
        "strict_budget": bool((defaults or {}).get("strict_budget", False)),
        "workload": (defaults or {}).get("workload", "general"),
        "battery_weight": int((defaults or {}).get("battery_weight", 1)),
        "portability_weight": int((defaults or {}).get("portability_weight", 3)),
    }
    mapped = []

    # Explicit limits are different from a preferred, flexible budget.
    if re.search(r"\b(no more than|at most|cannot exceed|must not exceed|strict budget|strictly under|strictly below|maximum budget)\b", lower):
        values["strict_budget"] = True
        mapped.append("strict budget limit")
    elif re.search(r"\b(around|about|roughly|approximately|ideally|preferably|flexible budget|could spend more|a little more)\b", lower):
        values["strict_budget"] = False
        mapped.append("flexible preferred budget")

    money = re.search(r"(?:chf\s*)?([0-9][0-9,.'’ ]*)\s*(?:chf|francs?)\b", lower)
    budget_multiplier = 1
    if not money:
        money = re.search(r"\b(?:under|below|less than|up to|no more than|budget(?: of)?|around|about)\s+(?:chf\s*)?([0-9][0-9,.'’ ]*)(?:\s*(k|grand|thousand))?\b(?!\s*kg)", lower)
        if money and money.group(2):
            budget_multiplier = 1000
    if money:
        values["budget"] = _parse_user_number(money.group(1)) * budget_multiplier
        mapped.append(f"budget → CHF {values['budget']:,.0f}")
    elif re.search(r"\b(relatively|fairly|somewhat|reasonably|quite|pretty|moderately)\s+(?:cheap|affordable|inexpensive|priced)\b|\b(good value|good deal|value for money|reasonable price|not too pricey|not break the bank|mid[- ]range|mid[- ]priced)\b", lower):
        values["budget"] = min(values["budget"], 1400)
        mapped.append(f"relatively affordable → budget up to CHF {values['budget']:,.0f}")
    elif re.search(r"\b(very cheap|really cheap|super cheap|dirt cheap|as cheap as possible|costs? as little as possible|cheapest)\b", lower):
        values["budget"] = min(values["budget"], 700)
        mapped.append(f"very cheap → budget up to CHF {values['budget']:,.0f}")
    elif re.search(r"\b(cheap(?:-ish)?|cheaper|affordable|inexpensive|budget[- ]friendly|low[- ]cost|bargain|save money|on a budget|tight budget)\b|not too expensive|not expensive|don't want to spend a lot|do not want to spend a lot", lower):
        values["budget"] = min(values["budget"], 1000)
        mapped.append(f"affordable → budget up to CHF {values['budget']:,.0f}")
    elif re.search(r"\b(price|budget|cost)\s+(?:is )?not a concern\b|\b(money is no object|money doesn't matter)\b", lower):
        values["budget"] = max(values["budget"], 5000)
        mapped.append(f"budget is flexible → up to CHF {values['budget']:,.0f}")
    elif re.search(r"\b(premium|high[- ]end|top[- ]of[- ]the[- ]line)\b", lower):
        values["budget"] = max(values["budget"], 2500)
        mapped.append(f"premium → budget up to CHF {values['budget']:,.0f}")

    # A workload changes the CPU/GPU mixture, not the price or marketing category.
    if re.search(r"\b(gam(?:e|es|ing)|3d rendering|3d design|3d modelling|3d modeling|gpu intensive|blender|cad)\b", lower):
        values["workload"] = "gaming"
        mapped.append("main task → games / 3D (GPU matters more)")
    elif re.search(r"\b(school|studying|study|office|documents|browsing|writing|email|everyday)\b", lower):
        values["workload"] = "general"
        mapped.append("main task → everyday work (CPU matters more)")

    explicit_perf = re.search(r"(?:performance|score)\s*(?:of|at least|above|over|:)?\s*(\d{1,3})\s*(?:/\s*100|%)?", lower)
    if explicit_perf:
        values["performance"] = max(20, min(100, float(explicit_perf.group(1))))
        mapped.append(f"performance → {values['performance']:.0f}/100")
    elif re.search(r"\b(relatively fast|fairly fast|reasonably fast|pretty fast|quite fast)\b", lower):
        values["performance"] = 72
        mapped.append("relatively fast → performance 72/100")
    elif re.search(r"\b(very fast|super fast|extremely fast|blazing fast|lightning fast|doesn't lag|does not lag|no lag|doesn't feel slow|does not feel slow)\b", lower):
        values["performance"] = 92
        mapped.append("very fast/no lag → performance 92/100")
    elif re.search(r"\b(gaming|video editing|3d rendering|3d design|cad|machine learning|heavy workloads?|powerful|fast|quick|snappy|responsive|smooth|quick to load|runs apps well|lots of tabs|many tabs|multitasking|workhorse)\b", lower):
        values["performance"] = 85
        mapped.append("fast/powerful or demanding work → performance 85/100")
    elif re.search(r"\b(programming|coding|developer|software development)\b", lower):
        values["performance"] = 70
        mapped.append("programming/coding → performance 70/100")
    elif re.search(r"\b(work from home|office work|video calls|streaming|watching movies|school|student|studying|everyday|normal use|web browsing|email|writing documents|documents and spreadsheets|basic|simple tasks?|light office)\b", lower):
        values["performance"] = 55
        mapped.append("everyday study/work → performance 55/100")

    # Preferences about *importance* can be said in words, too.
    # Source data contains battery CAPACITY, so we never promise runtime hours.
    if re.search(r"\b(battery (?:doesn.t|does not) matter|battery not important|don.t care about battery)\b", lower):
        values["battery_weight"] = 0
        mapped.append("battery size → not important")
    elif re.search(r"\b(long battery|good battery|battery life|battery important|long lasting battery|all.day battery)\b", lower):
        values["battery_weight"] = 5
        mapped.append("battery capacity → important (runtime not measured)")
    if re.search(r"\b(weight (?:doesn.t|does not) matter|don.t care about weight|portability not important)\b", lower):
        values["portability_weight"] = 0
        mapped.append("portability → not important")

    explicit_weight = re.search(r"(\d+(?:[.,]\d+)?)\s*kg\b", lower)
    if explicit_weight:
        values["weight"] = _parse_user_number(explicit_weight.group(1))
        mapped.append(f"weight limit → {values['weight']:g} kg")
    elif re.search(r"\b(ultralight|very light|as light as possible)\b", lower):
        values["weight"] = 1.2
        mapped.append("very light → maximum 1.2 kg")
    elif re.search(r"\b(relatively light|fairly light|not too heavy)\b", lower):
        values["weight"] = 1.6
        mapped.append("relatively light → maximum 1.6 kg")
    elif re.search(r"\b(lightweight|easy to carry|carry it around|travel[- ]friendly|portable|commut(?:e|ing)|backpack)\b", lower):
        values["weight"] = 1.4
        mapped.append("lightweight/travel-friendly → maximum 1.4 kg")
    elif re.search(r"\b(desk|desktop replacement|stays at home|weight does not matter|heavy is fine)\b", lower):
        values["weight"] = 2.8
        mapped.append("weight is not a concern → maximum 2.8 kg")

    for key, patterns, label in (
        ("os", (r"\bmacos\b", r"\bmac os\b", r"\bmacbook\b", r"\bmac\b"), "macOS"),
        ("os", (r"\bwindows\b",), "Windows"),
        ("os", (r"\blinux\b", r"\bubuntu\b"), "Linux"),
    ):
        if any(re.search(pattern, lower) for pattern in patterns):
            values["os"] = label
            mapped.append(f"operating system → {label}")
            break

    compat = re.search(r"\b(usb-c|usb-a|thunderbolt|hdmi|cuda|touchscreen)\b", lower)
    if compat:
        feature = compat.group(1).upper() if compat.group(1).startswith("usb") else compat.group(1).title()
        mapped.append(f"{feature}: not verifiable in demo catalog; not used for filtering")
        values["compatibility"] = "Any"

    return {"values": values, "mapped": mapped}


def _parse_user_number(value: str) -> float:
    cleaned = value.replace("'", "").replace("’", "").replace(" ", "")
    if "," in cleaned and "." in cleaned:
        decimal_mark = "," if cleaned.rfind(",") > cleaned.rfind(".") else "."
        thousands_mark = "." if decimal_mark == "," else ","
        cleaned = cleaned.replace(thousands_mark, "").replace(decimal_mark, ".")
    elif "," in cleaned:
        left, right = cleaned.rsplit(",", 1)
        cleaned = left + right if len(right) == 3 else left + "." + right
    return float(cleaned)


def read_number(prompt: str, default: float) -> float:
    value = input(f"{prompt} [{default}]: ").strip()
    return float(value) if value else default


def cli_main() -> None:
    print("\nFuzzy Laptop Advisor")
    print("Tell us what matters. Scores are fuzzy suitability estimates, not product ratings.\n")
    budget = read_number("Preferred budget (CHF)", 1500)
    min_performance = read_number("Desired performance (0–100)", 65)
    max_weight = read_number("Preferred maximum weight (kg)", 1.8)
    print("\nSet importance from 1 (less important) to 5 (most important).")
    weights = {
        "Price": read_number("Price importance", 4),
        "Performance": read_number("Performance importance", 4),
        "Portability": read_number("Portability importance", 3),
        "Battery size": read_number("Battery size importance (0 = ignore)", 1),
    }
    os_choice = input("Required operating system (Windows/macOS/Linux/Any) [Any]: ").strip() or "Any"
    compat = input("Required compatibility keyword, or Any [Any]: ").strip() or "Any"
    strict = input("Hard budget limit? (y/N): ").strip().lower() == "y"
    workload = input("Main tasks (general/gaming) [general]: ").strip().lower() or "general"
    prefs = Preferences(budget, min_performance, max_weight, weights, os_choice, compat, strict, workload)

    try:
        recommendations = rank_laptops(load_laptops(), prefs)
    except (ValueError, OSError) as exc:
        print(f"\nCould not load laptop catalog: {exc}")
        return
    if not recommendations:
        print("\nNo catalog laptops meet all hard requirements. Try widening the budget or constraints.")
        return

    print("\nTop recommendations")
    for rank, result in enumerate(recommendations[:5], 1):
        laptop = result["laptop"]
        print(f"\n{rank}. {laptop.name} — {result['score']:.0%} fuzzy match")
        print(f"   CHF {laptop.price_chf:.0f} | {result['performance_index']:.0f}/100 estimated performance | "
              f"{laptop.weight_kg:.2f} kg | {laptop.operating_system}")
        print("   Suitability: " + " · ".join(f"{name} {value:.0%}" for name, value in result["memberships"].items()))
        print("   Score contribution: " + " · ".join(f"{name} +{value:.0%}" for name, value in result["contributions"].items()))


WEB_ROOT = Path(__file__).with_name("web")


class AdvisorHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/catalog-info":
            try:
                laptops = load_laptops()
                self._json(200, {"count": len(laptops), "warnings": LOAD_WARNINGS})
            except (ValueError, OSError) as exc:
                self._json(400, {"error": str(exc)})
            return
        target = WEB_ROOT / ("index.html" if self.path in ("/", "/index.html") else self.path.lstrip("/"))
        if not target.is_file() or WEB_ROOT not in target.resolve().parents:
            self.send_error(404)
            return
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(str(target))[0] or "application/octet-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path == "/interpret":
            try:
                payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
                if not isinstance(payload, dict) or not isinstance(payload.get("defaults", {}), dict):
                    raise ValueError("Expected JSON object with object defaults")
                result = interpret_request(str(payload.get("text", "")), payload.get("defaults", {}))
                self._json(200, result)
            except (ValueError, OSError, json.JSONDecodeError) as exc:
                self._json(400, {"error": str(exc)})
            return
        if self.path != "/recommend":
            self.send_error(404)
            return
        try:
            payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
            if not isinstance(payload, dict):
                raise ValueError("Expected a JSON object")
            prefs = Preferences(
                budget_chf=float(payload["budget"]), min_performance=float(payload["performance"]),
                max_weight_kg=float(payload["weight"]),
                weights={"Price": float(payload["priceWeight"]), "Performance": float(payload["performanceWeight"]),
                         "Portability": float(payload["portabilityWeight"]),
                         "Battery size": float(payload.get("batteryWeight", 0))},
                operating_system=payload.get("os", "Any"), compatibility=payload.get("compatibility", "Any"),
                strict_budget=payload.get("strictBudget", False) is True,
                workload=payload.get("workload", "general"),
            )
            results = rank_laptops(load_laptops(), prefs)
            answer = [{"name": result["laptop"].name, "price": result["laptop"].price_chf,
                       "performance": round(result["performance_index"], 1),
                       "cpu": result["laptop"].cpu_model,
                       "gpu": result["laptop"].gpu_model,
                       "ram": result["laptop"].ram_gb,
                       "storage": result["laptop"].storage_gb,
                       "batteryWh": result["laptop"].battery_wh,
                       "weight": result["laptop"].weight_kg, "os": result["laptop"].operating_system,
                       "score": result["score"], "baseScore": result["base_score"], "memberships": result["memberships"],
                       "contributions": result["contributions"],
                       "explanation": result["explanation"],
                       "budgetFactor": result["budget_factor"],
                       "gpuFactor": result["gpu_factor"],
                       "ruleStrengths": result["rule_strengths"],
                       "warnings": result["warnings"]} for result in results]
            self._json(200, {"results": answer})
        except (ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
            self._json(400, {"error": str(exc)})

    def _json(self, status, data):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    if "--cli" in sys.argv:
        cli_main()
        return
    server = ThreadingHTTPServer(("127.0.0.1", 8000), AdvisorHandler)
    print("Fuzzy Laptop Advisor is running at http://127.0.0.1:8000")
    print("Press Ctrl+C to stop. Use --cli to run the terminal version.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
