import unittest
from adaptive_historical import report_identity

class ReportIdentity(unittest.TestCase):
    def test_rejects_mislabelled_report(self):
        plan=dict(candidateId="c",buildId="b",sourceRevision="r",dirty=True)
        saved=dict(plan,pilot=False);report_identity(saved,plan,False)
        for key,value in (("candidateId","other"),("buildId","other"),("sourceRevision","other"),("dirty",False),("dirty",1),("pilot",True),("pilot",0)):
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):report_identity(dict(saved,**{key:value}),plan,False)
if __name__=="__main__":unittest.main()
