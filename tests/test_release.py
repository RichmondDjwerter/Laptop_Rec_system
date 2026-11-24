"""Final-release smoke and input validation tests (standard-library only)."""
import csv
from pathlib import Path
import sys
import unittest
from urllib.request import urlopen, Request
from urllib.error import HTTPError
from threading import Thread
from http.server import ThreadingHTTPServer
import json

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import main
from evaluation.summarize_pilot import report as pilot_report
from evaluation.run_ablation import make_report

class ReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), main.AdvisorHandler)
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.server.server_port}'
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)
    def post(self,path,body):
        req=Request(self.base+path, data=json.dumps(body).encode(),headers={'Content-Type':'application/json'}, method='POST')
        with urlopen(req,timeout=3) as f: return json.load(f)
    def test_catalog_and_site(self):
        with urlopen(self.base+'/catalog-info') as f:
            payload=json.load(f)
        self.assertEqual(payload['count'],56)
        self.assertFalse(payload['warnings'])
        with urlopen(self.base+'/') as f:
            self.assertIn(b'compareTray', f.read())
    def test_api_recommendation_breakdown(self):
        body=self.post('/recommend',{'budget':1100,'performance':80,'weight':2,'priceWeight':3,'performanceWeight':5,'portabilityWeight':2,'batteryWeight':1,'workload':'gaming','os':'Any','strictBudget':False})
        self.assertEqual(len(body['results']),56)
        for item in body['results']:
            self.assertIn('baseScore',item)
            self.assertAlmostEqual(item['score'],item['baseScore']*item['budgetFactor']*item['gpuFactor'])
            self.assertGreaterEqual(item['score'],0)
            self.assertLessEqual(item['score'],1)
    def test_api_strict_budget(self):
        body=self.post('/recommend',{'budget':800,'performance':80,'weight':2,'priceWeight':3,'performanceWeight':5,'portabilityWeight':2,'batteryWeight':1,'workload':'general','os':'Any','strictBudget':True})
        self.assertTrue(body['results'])
        self.assertTrue(all(x['price']<=800 for x in body['results']))
    def test_api_language(self):
        parsed=self.post('/interpret',{'text':'around 1100 CHF, gaming laptop, long battery, weight does not matter'})
        vals=parsed['values']
        self.assertEqual(vals['workload'],'gaming')
        self.assertEqual(vals['budget'],1100)
        self.assertEqual(vals['portability_weight'],0)
        self.assertEqual(vals['battery_weight'],5)
    def test_api_rejects_invalid_budget(self):
        params={'budget':0,'performance':80,'weight':2,'priceWeight':3,'performanceWeight':5,'portabilityWeight':2,'batteryWeight':1}
        req=Request(self.base+'/recommend',data=json.dumps(params).encode(),headers={'Content-Type':'application/json'},method='POST')
        with self.assertRaises(HTTPError) as cm: urlopen(req,timeout=3)
        self.assertEqual(cm.exception.code,400)
    def test_pilot_empty_and_ablation_reproducible(self):
        self.assertIn('NOT CONDUCTED', pilot_report())
        self.assertIn('Model component ablation', make_report())
    def test_catalog_no_duplicates(self):
        with (ROOT/'laptops.csv').open(newline='',encoding='utf-8') as f:
            rows=list(csv.DictReader(f))
        self.assertEqual(len(rows),56)
        self.assertEqual(len({r['name'].casefold() for r in rows}),56)

if __name__=='__main__': unittest.main()
