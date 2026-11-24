# Fuzzy Laptop Advisor

A small university prototype that helps people choose a laptop without needing to understand every technical specification. Instead of relying on labels like *Student*, *Business*, or *Gaming*, the site compares hardware and lets users describe what matters to them.

## Run locally

Python 3.10+ is enough; no extra packages are required.

```bash
python main.py
```

Open **http://127.0.0.1:8000**. Stop the server with `Ctrl+C`.

## How it works

Users can enter preferences using **sliders** or a short **English description**, for example: *“A fairly affordable laptop for gaming, with good performance; weight doesn't matter.”* The site turns recognised phrases into editable settings.

- **Preferences:** budget, performance, portability, battery size, and their importance (0–5).
- **Main tasks:** everyday work/study or gaming/3D. These use different CPU/GPU weightings.
- **Flexible budget:** slightly more expensive laptops can still be considered. **Strict budget** is available when the limit is absolute.
- **Results:** ranked laptop cards, a short explanation for each match, and side-by-side comparison of two options.

Each laptop receives a fuzzy suitability value between 0 and 1 for every selected criterion. We combine these values with the user's importance weights:

\[
S_{base}(L) = \frac{\sum_i w_i\,\mu_i(L)}{\sum_i w_i}
\]

A smooth budget adjustment discourages large price overruns. A small fuzzy rule also accounts for weak graphics when gaming/3D performance matters. The final score measures **preference fit**, not the probability of a good purchase.

## Project files

| File | Purpose |
|---|---|
| `main.py` | Data loading, preference interpretation, fuzzy scoring, recommendations, and local server |
| `laptops.csv` | One active demonstration catalog with 56 configurations |
| `web/index.html` | Website layout |
| `web/app.js` | Controls, results, explanations, and comparisons |
| `web/style.css` | Styling and responsive layout |
| `tests/` | Automated tests |
| `evaluation/` | Scripts for technical comparisons, ablation, and a small user pilot |

## Testing

From the project folder:

```bash
python -m unittest discover -s tests -v
python evaluation/run_evaluation.py
python evaluation/run_ablation.py
```

The evaluation scripts generate their own Markdown result files. Our technical tests use constructed scenarios and are separate from testing with real users.

## Data and limitations

The catalog contains **56 example configurations** based on a [cleaned Smartprix laptop dataset](https://github.com/krrishrana962-DATA/Smartprix-Laptop-Dataset---Data-Cleaning). Prices in CHF and CPU/GPU performance indices are **approximate demonstration values**, not current store offers or measured benchmarks. Battery capacity (Wh) is not battery runtime (hours). The membership-function boundaries are prototype settings and still need user feedback.

## Background

- Portmann et al., *Fuzzy Sets and Systems I* (2026), “Approximative Measurements,” pp. 31–35 — fuzzification and fuzzy rules.
- Portmann et al., *Fuzzy Sets and Systems II* (2026), “Customer Classification,” pp. 60–64 — linguistic variables and combining criteria.
- vom Brocke, Hevner & Maedche, *Introduction to Design Science Research* (2020), pp. 3–6 — building, demonstrating, and evaluating a prototype.
