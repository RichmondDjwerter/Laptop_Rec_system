"""Small regression suite for the integrated recommendation engine."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main


class RecommendationTests(unittest.TestCase):
    def setUp(self):
        self.prefs = main.Preferences(
            1300, 85, 2.5,
            {"Price": 2, "Performance": 5, "Portability": 1}
        )
        self.a = main.Laptop('Within preferred budget', 1290, 72, 1.8, 'Windows', '')
        self.b = main.Laptop('Better for 100 more', 1390, 95, 1.4, 'Windows', '')

    def test_flexible_vs_strict(self):
        ranked = main.rank_laptops([self.a, self.b], self.prefs)
        self.assertEqual(ranked[0]['laptop'].name, self.b.name)
        strict = main.Preferences(1300, 85, 2.5, self.prefs.weights, strict_budget=True)
        self.assertEqual(len(main.rank_laptops([self.a, self.b], strict)), 1)

    def test_price_continuity(self):
        self.assertAlmostEqual(main.price_membership(1299.99, 1300),
                               main.price_membership(1300.01, 1300), delta=0.001)
        self.assertGreater(main.price_membership(1300, 1300), 0.0)
        self.assertGreater(main.price_membership(1390, 1300), 0.0)

    def test_monotonic_scores(self):
        for v in [600, 1000, 1290, 1300, 1390, 1600, 2000]:
            self.assertGreaterEqual(main.price_membership(v, 1300),
                                    main.price_membership(v + 1, 1300))
        for v in [20, 50, 80, 85, 95]:
            self.assertLessEqual(main.performance_membership(v, 85),
                                 main.performance_membership(v + 1, 85))
        for v in [1, 1.3, 1.7, 2.3, 2.7]:
            self.assertGreaterEqual(main.portability_membership(v, 2.5),
                                    main.portability_membership(v + .01, 2.5))

    def test_criteria_importance(self):
        important_price = main.Preferences(1300, 85, 2.5,
                            {'Price': 5, 'Performance': 1, 'Portability': 1})
        scores1 = main.rank_laptops([self.a, self.b], self.prefs)
        scores2 = main.rank_laptops([self.a, self.b], important_price)
        self.assertNotEqual([x['laptop'].name for x in scores1],
                            [x['laptop'].name for x in scores2])

    def test_os_alias(self):
        mac = main.Laptop('Mac laptop', 1000, 80, 1.2, 'Mac OS', '')
        pref = main.Preferences(1300, 85, 2.5, self.prefs.weights, 'macOS')
        self.assertTrue(main.meets_constraints(mac, pref))

    def test_integrated_modern_catalog_loads(self):
        laptops = main.load_laptops()
        self.assertGreaterEqual(len(laptops), 55)
        self.assertEqual(len(main.LOAD_WARNINGS), 0)
        for laptop in laptops:
            self.assertGreater(laptop.price_chf, 0)
            self.assertTrue(laptop.cpu_model)
            self.assertTrue(laptop.gpu_model)
            self.assertGreater(laptop.ram_gb, 0)
            self.assertGreater(laptop.battery_wh, 0)
            self.assertGreater(laptop.cpu_index, 0)
            self.assertGreater(laptop.gpu_index, 0)
            self.assertGreater(laptop.weight_kg, 0)
        self.assertTrue(main.rank_laptops(laptops, self.prefs))

    def test_catalog_unique_and_varied(self):
        laptops = main.load_laptops()
        self.assertEqual(len({x.name.casefold() for x in laptops}), len(laptops))
        self.assertTrue(any('MacBook' in x.name for x in laptops))
        self.assertTrue(any('RTX 4080' in x.gpu_model for x in laptops))
        self.assertTrue(any('GTX 1650' in x.gpu_model for x in laptops))
        self.assertGreaterEqual(len([x for x in laptops if x.price_chf < 850]), 10)

    def test_fuzzy_min_and_caution_monotonicity(self):
        prefs = main.Preferences(1100, 85, 2.8, {'Price':2,'Performance':5,'Portability':0,'Battery size':0},workload='gaming')
        def item(gpu):
            return main.Laptop('GPU Test',1000,80,2,'Windows','',ram_gb=16,cpu_index=75,gpu_index=gpu,battery_wh=65)
        slow=main.fuzzy_rule_cautions(item(25),prefs)
        fast=main.fuzzy_rule_cautions(item(85),prefs)
        self.assertGreater(slow['Gaming GPU caution'],fast['Gaming GPU caution'])
        r=main.rank_laptops([item(25),item(85)],prefs)
        self.assertEqual(r[0]['laptop'].gpu_index,85)
        self.assertLess(r[-1]['gpu_factor'],1)
        self.assertEqual(r[0]['gpu_factor'],1)

    def test_fuzzy_rule_only_applies_to_gaming(self):
        laptop=main.Laptop('GPU Test',1000,80,2,'Windows','',ram_gb=16,cpu_index=75,gpu_index=25,battery_wh=65)
        weights={'Price':2,'Performance':5,'Portability':0,'Battery size':0}
        general=main.Preferences(1100,85,2.8,weights,workload='general')
        gaming=main.Preferences(1100,85,2.8,weights,workload='gaming')
        self.assertEqual(main.rank_laptops([laptop],general)[0]['gpu_factor'],1)
        self.assertLess(main.rank_laptops([laptop],gaming)[0]['gpu_factor'],1)

    def test_rule_activations_bounded(self):
        laptops=main.load_laptops()
        for work in ('general','gaming'):
            prefs=main.Preferences(950,85,1.8,{'Price':4,'Performance':5,'Portability':3,'Battery size':1},workload=work)
            for laptop in laptops:
                x=main.rank_laptops([laptop],prefs)[0]
                self.assertTrue(0 <= x['score'] <= 1)
                self.assertTrue(all(0<=v<=1 for v in x['rule_strengths'].values()))
                self.assertAlmostEqual(x['score'],x['base_score']*x['budget_factor']*x['gpu_factor'])

    def test_pareto_dominance_identical_other_features(self):
        weights={'Price':3,'Performance':5,'Portability':2,'Battery size':1}
        prefs=main.Preferences(1000,80,2.5,weights,workload='gaming')
        cheap=main.Laptop('Dominates',950,80,1.8,'Windows','',ram_gb=16,cpu_index=75,gpu_index=76,battery_wh=70)
        worse=main.Laptop('Dominated',1100,80,2.1,'Windows','',ram_gb=16,cpu_index=65,gpu_index=43,battery_wh=60)
        self.assertEqual(main.rank_laptops([cheap,worse],prefs)[0]['laptop'].name,'Dominates')

    def test_workload_changes_performance_by_cpu_gpu(self):
        laptops = main.load_laptops()
        model = next(x for x in laptops if 'Aspire 7' in x.name)
        general = main.laptop_performance(model, 'general')
        gaming = main.laptop_performance(model, 'gaming')
        self.assertNotAlmostEqual(general, gaming)

    def test_price_overrun_is_not_hard_cutoff(self):
        normal = main.Preferences(1000, 85, 2.5,
                      {'Price':2, 'Performance':5, 'Portability':1, 'Battery size':1})
        prices = [1000, 1200, 1300, 1600, 4000]
        factors = [main.severe_overrun_factor(x, 1000, 2) for x in prices]
        self.assertEqual(factors[:2], [1.0, 1.0])
        self.assertTrue(all(a >= b for a,b in zip(factors, factors[1:])))
        self.assertGreater(factors[-1], 0)
        self.assertLess(factors[-1], 0.01)
        self.assertEqual(main.severe_overrun_factor(4000, 1000, 0), 1)
        laptops = main.load_laptops()
        result = main.rank_laptops(laptops, normal)
        self.assertEqual(result[0]['laptop'].name, 'Xiaomi Redmi G Pro 2024 Gaming Laptop')
        self.assertGreater(result[0]['score'], result[-1]['score'])
        self.assertNotIn('Legion 9i', result[0]['laptop'].name)

    def test_budget_above_preference_can_win(self):
        results = main.rank_laptops([self.a, self.b], self.prefs)
        self.assertEqual(results[0]['laptop'], self.b)
        self.assertAlmostEqual(results[0]['budget_factor'], 1.0)

    def test_ignore_battery_weight(self):
        prefs = main.Preferences(1200, 70, 2, {'Price':4,'Performance':4,'Portability':3,'Battery size':0})
        a = main.Laptop('A',1000,80,1.6,'Windows','',battery_wh=40)
        b = main.Laptop('B',1000,80,1.6,'Windows','',battery_wh=99)
        ranked = main.rank_laptops([a,b],prefs)
        self.assertAlmostEqual(ranked[0]['score'],ranked[1]['score'])

    def test_natural_language_battery_and_weight_importance(self):
        parsed = main.interpret_request('long battery but weight does not matter')
        self.assertEqual(parsed['values']['battery_weight'],5)
        self.assertEqual(parsed['values']['portability_weight'],0)

    def test_natural_language_gaming_workload(self):
        r = main.interpret_request('gaming, around 1000 CHF')
        self.assertEqual(r['values']['workload'],'gaming')
        self.assertEqual(r['values']['budget'],1000)


    def test_text_interpreter(self):
        parsed = main.interpret_request('around 1300 CHF for a fast laptop')
        self.assertFalse(parsed['values']['strict_budget'])
        strict = main.interpret_request('no more than 1300 CHF for a fast laptop')
        self.assertTrue(strict['values']['strict_budget'])


if __name__ == '__main__':
    unittest.main()
