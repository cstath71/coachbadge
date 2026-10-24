import os, unittest
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
class T(unittest.TestCase):
    def test_daily_rebuild(self):
        s=open(os.path.join(ROOT,".github/workflows/pages.yml")).read()
        self.assertIn("cron: '5 23 * * *'",s)
        self.assertIn("workflow_dispatch",s); self.assertIn("push:",s)
        self.assertIn('--today "$(TZ=Europe/Zurich date +%F)"',s)
        for bad in ("fetch","indexnow","newsletter","send"):
            self.assertNotIn(bad, s.split("jobs:")[1].lower())
