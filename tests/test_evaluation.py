"""Technical model safeguards and baseline comparison (no external packages)."""
from dataclasses import replace
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from evaluation.run_evaluation import (SCENARIOS, crisp_baseline, jaccard,
                                       pareto_violations, sensitivity)
import main


class EvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.laptops = main.load_laptops()
        assert not main.LOAD_WARNINGS

    def test_crisp_matches_only_ranked_eligible_items(self):
        for sc in SCENARIOS:
            p = sc.preferences()
            fuzzy = main.rank_laptops(self.laptops, p)
            crisp = crisp_baseline(self.laptops, p)
            fuzzy_names = {r['laptop'].name for r in fuzzy}
            self.assertTrue(all(r['laptop'].name in fuzzy_names for r in crisp))
            for r in crisp:
                l = r['laptop']
                self.assertLessEqual(l.price_chf, p.budget_chf)
                self.assertGreaterEqual(r['performance_index'], p.min_performance)
                self.assertLessEqual(l.weight_kg, p.max_weight_kg)

    def test_strict_budget_on_real_catalog(self):
        sc = next(s for s in SCENARIOS if s.strict)
        for r in main.rank_laptops(self.laptops, sc.preferences()):
            self.assertLessEqual(r['laptop'].price_chf, sc.budget)

    def test_expected_demo_baseline_empty_and_near_matches_available(self):
        sc = SCENARIOS[0]
        self.assertEqual(len(crisp_baseline(self.laptops, sc.preferences())), 0)
        fuzzy = main.rank_laptops(self.laptops, sc.preferences())
        self.assertGreaterEqual(len(fuzzy), 50)
        self.assertGreater(fuzzy[0]['score'], .5)

    def test_monotonicity_under_changes_to_one_feature(self):
        # Model should never penalize a strictly better hardware or price
        # input with all others unchanged, given the fixed illustrative indices.
        changes = [
            lambda l: replace(l, price_chf=max(1, l.price_chf - 50)),
            lambda l: replace(l, weight_kg=max(.3, l.weight_kg - .2)),
            lambda l: replace(l, battery_wh=l.battery_wh + 10),
            lambda l: replace(l, cpu_index=min(100, l.cpu_index + 5)),
            lambda l: replace(l, gpu_index=min(100, l.gpu_index + 5)),
            lambda l: replace(l, ram_gb=l.ram_gb + 8),
        ]
        for sc in SCENARIOS:
            # Avoid a strict price filter that could remove a reference item.
            p = sc.preferences(strict_budget=False)
            for laptop in self.laptops:
                old = main.rank_laptops([laptop], p)[0]['score']
                for upgrade in changes:
                    new = main.rank_laptops([upgrade(laptop)], p)[0]['score']
                    self.assertGreaterEqual(new + 1e-10, old,
                         f'Unexpected worse fit for {laptop.name} in {sc.title}')

    def test_marketing_label_does_not_affect_score(self):
        base = main.Laptop('Office / Student', 850, 65, 1.8, 'Windows', '',
                           ram_gb=16, cpu_index=75, gpu_index=60, battery_wh=55)
        twin = replace(base, name='Extreme Gaming Pro')
        for sc in SCENARIOS:
            a, b = main.rank_laptops([base, twin], sc.preferences())
            self.assertAlmostEqual(a['score'], b['score'])

    def test_pareto_and_sensitivity_can_be_reproduced(self):
        comparisons, problems = pareto_violations(self.laptops, SCENARIOS[0])
        self.assertGreater(comparisons, 0)
        self.assertFalse(problems)
        for sc in SCENARIOS:
            variants = sensitivity(self.laptops, sc)
            self.assertGreater(len(variants), 0)
            for _, _, overlap in variants:
                self.assertTrue(0 <= overlap <= 1)

    def test_jaccard(self):
        self.assertEqual(jaccard([], []), 1)
        self.assertEqual(jaccard(['x', 'y'], ['y', 'x']), 1)
        self.assertEqual(jaccard(['x'], ['y']), 0)
        self.assertAlmostEqual(jaccard(['x', 'y'], ['y', 'z']), 1/3)


if __name__ == '__main__':
    unittest.main()
