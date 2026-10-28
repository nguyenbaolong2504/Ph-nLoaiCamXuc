import copy
import unittest
from backend.app.analysis import Smoother
from backend.app.security import hash_password,verify_password

class CoreTests(unittest.TestCase):
    def test_password_salted_and_checked(self):
        a=hash_password('strong-password');b=hash_password('strong-password')
        self.assertNotEqual(a,b);self.assertTrue(verify_password('strong-password',a));self.assertFalse(verify_password('wrong',a))

    def test_smoothing_matches_geometry_and_resets_on_no_face(self):
        labels=['angry','disgust','fear','happy','neutral','sad','surprise']
        def face(box,label):
            return {'box':box,'face_id':1,'scores':{k:1.0 if k==label else 0.0 for k in labels},'score':1.,'expression':label,'status':'OK','quality':'OK'}
        smooth=Smoother()
        first=smooth.apply({'faces':[face([0,0,100,100],'happy'),face([300,0,100,100],'sad')]},.6)
        ids=[f['face_id'] for f in first['faces']]
        second=smooth.apply({'faces':[face([302,0,100,100],'sad'),face([2,0,100,100],'happy')]},.6)
        self.assertEqual([f['face_id'] for f in second['faces']],ids[::-1])
        smooth.apply({'faces':[]},.6)
        third=smooth.apply({'faces':[face([0,0,100,100],'happy')]},.6)
        self.assertNotIn(third['faces'][0]['face_id'],ids)

if __name__=='__main__':unittest.main()
