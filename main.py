"""Fuzzy Laptop Advisor: explainable fuzzy ranking with hard constraints."""

from __future__ import annotations

import csv
import io
import json
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


@dataclass(frozen=True)
class Preferences:
    budget_chf: float
    min_performance: float
    max_weight_kg: float
    weights: dict[str, float]
    operating_system: str = "Any"
    compatibility: str = "Any"


def ramp(value: float, low: float, high: float) -> float:
    """Linear fuzzy membership from 0 at low to 1 at high."""
    if high <= low:
        raise ValueError("high must be greater than low")
    return max(0.0, min(1.0, (value - low) / (high - low)))


def price_membership(price: float, budget: float) -> float:
    """Affordable membership: fully suitable below 75% of budget, then fades."""
    return max(0.0, min(1.0, (budget - price) / (budget * 0.25))) if budget > 0 else 0.0


def memberships(laptop: Laptop, prefs: Preferences) -> dict[str, float]:
    """Convert technical measurements into 0–1 fuzzy suitability degrees."""
    scores = {
        "Price": price_membership(laptop.price_chf, prefs.budget_chf),
        "Performance": ramp(laptop.performance, prefs.min_performance * 0.65, prefs.min_performance * 1.25),
        # Lower weight is better, so reverse the increasing ramp.
        "Portability": 1.0 - ramp(laptop.weight_kg, prefs.max_weight_kg * 0.7, prefs.max_weight_kg * 1.5),
    }
    return scores


def meets_constraints(laptop: Laptop, prefs: Preferences) -> bool:
    return (
        laptop.price_chf <= prefs.budget_chf
        and (prefs.operating_system == "Any" or laptop.operating_system.casefold() == prefs.operating_system.casefold())
        and (prefs.compatibility.casefold() == "any" or prefs.compatibility.casefold() in laptop.compatibility.casefold())
    )


def rank_laptops(laptops: list[Laptop], prefs: Preferences) -> list[dict]:
    eligible = [laptop for laptop in laptops if meets_constraints(laptop, prefs)]
    total_weight = sum(prefs.weights.values())
    if total_weight <= 0 or any(weight < 0 for weight in prefs.weights.values()):
        raise ValueError("Preference weights must be non-negative and have a positive total")

    results = []
    for laptop in eligible:
        scores = memberships(laptop, prefs)
        included_weight = sum(prefs.weights[key] for key in scores)
        contributions = {key: scores[key] * prefs.weights[key] / included_weight for key in scores} if included_weight else {}
        results.append({
            "laptop": laptop,
            "score": sum(contributions.values()),
            "memberships": scores,
            "contributions": contributions,
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
    }
    mapped = []

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
        values["compatibility"] = compat.group(1).upper() if compat.group(1).startswith("usb") else compat.group(1).title()
        mapped.append(f"must-have feature → {values['compatibility']}")

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
    budget = read_number("Maximum budget (CHF)", 1500)
    min_performance = read_number("Desired performance (0–100)", 65)
    max_weight = read_number("Preferred maximum weight (kg)", 1.8)
    print("\nSet importance from 1 (less important) to 5 (most important).")
    weights = {
        "Price": read_number("Price importance", 4),
        "Performance": read_number("Performance importance", 4),
        "Portability": read_number("Portability importance", 3),
    }
    os_choice = input("Required operating system (Windows/macOS/Linux/Any) [Any]: ").strip() or "Any"
    compat = input("Required compatibility keyword, or Any [Any]: ").strip() or "Any"
    prefs = Preferences(budget, min_performance, max_weight, weights, os_choice, compat)

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
        print(f"   CHF {laptop.price_chf:.0f} | {laptop.performance:.0f}/100 performance | "
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
            prefs = Preferences(
                budget_chf=float(payload["budget"]), min_performance=float(payload["performance"]),
                max_weight_kg=float(payload["weight"]),
                weights={"Price": float(payload["priceWeight"]), "Performance": float(payload["performanceWeight"]),
                         "Portability": float(payload["portabilityWeight"])},
                operating_system=payload.get("os", "Any"), compatibility=payload.get("compatibility", "Any"),
            )
            results = rank_laptops(load_laptops(), prefs)
            answer = [{"name": result["laptop"].name, "price": result["laptop"].price_chf,
                       "performance": result["laptop"].performance,
                       "weight": result["laptop"].weight_kg, "os": result["laptop"].operating_system,
                       "score": result["score"], "memberships": result["memberships"],
                       "contributions": result["contributions"]} for result in results]
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
