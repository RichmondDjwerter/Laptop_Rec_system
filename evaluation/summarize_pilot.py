"""Summarize anonymous feedback collected during our small user test."""

import csv
from pathlib import Path
from statistics import mean, median

FOLDER = Path(__file__).resolve().parent
INPUT = FOLDER / "participant_responses.csv"
OUTPUT = FOLDER / "USER_RESULTS.md"

QUESTIONS = {
    "understood_why": "Understanding the recommendation",
    "understood_tradeoffs": "Understanding the trade-offs",
    "confidence": "Confidence in the choice",
    "ease_of_use": "Ease of use",
}


def clean(value):
    return (str(value or "").replace("|", "/").replace("\n", " ")
            .replace("\r", " ").replace("<", "&lt;").replace(">", "&gt;").strip())


def report(path=INPUT):
    with Path(path).open(encoding="utf-8-sig", newline="") as file:
        responses = list(csv.DictReader(file))

    lines = ["# User test — Fuzzy Laptop Advisor", ""]
    if not responses:
        return "\n".join(lines + [
            "**Status: NOT CONDUCTED**", "",
            "We have not collected participant responses yet. "
            "This report will be filled after the user test.", "",
        ])

    ids = [str(row.get("participant_id") or "").strip() for row in responses]
    if not all(ids) or len(set(ids)) != len(ids):
        raise ValueError("Participant IDs must be non-empty and unique.")

    completed = sum(str(row.get("completed") or "").strip().lower()
                    in ("yes", "y", "true", "1") for row in responses)
    lines += [
        f"We collected feedback from **{len(responses)} participants**.", "",
        f"- Completed the laptop-choice task: **{completed}/{len(responses)}**.", "",
        "## Ratings (1 = low, 5 = high)", "",
    ]
    for field, label in QUESTIONS.items():
        values = []
        for row in responses:
            raw = str(row.get(field) or "").strip()
            if not raw:
                continue
            rating = int(raw)
            if not 1 <= rating <= 5:
                raise ValueError(f"{field} must be between 1 and 5.")
            values.append(rating)
        if values:
            lines.append(f"- {label}: {mean(values):.1f}/5 on average "
                         f"(median {median(values):g}, n={len(values)}).")
        else:
            lines.append(f"- {label}: no answers yet.")

    times = [float(row["decision_seconds"]) for row in responses
             if str(row.get("decision_seconds") or "").strip()]
    if times:
        if min(times) < 0:
            raise ValueError("Decision times cannot be negative.")
        lines.append(f"- Typical task time: {median(times):.0f} seconds "
                     f"(n={len(times)}).")

    lines += ["", "## Comments", ""]
    for row in responses:
        details = []
        for field, label in (("chosen_model", "Choice"),
                             ("one_advantage", "Liked"),
                             ("one_disadvantage", "Disliked"),
                             ("confusion", "Confusing")):
            value = clean(row.get(field))
            if value:
                details.append(f"{label}: {value}")
        lines.append(f"- **{clean(row['participant_id'])}:** " +
                     ("; ".join(details) if details else "No written comments."))

    lines += ["", "These results describe only the people we tested. "
              "They are not proof that the system works equally well for everyone.", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    OUTPUT.write_text(report(), encoding="utf-8")
    print(f"Saved: {OUTPUT.name}")
