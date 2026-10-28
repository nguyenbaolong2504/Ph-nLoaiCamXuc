"""Integration tests against the running app and its REAL MongoDB/model.
Run: python -m unittest discover -s tests -p 'test_*.py' -v
"""
import asyncio
import io
import json
import os
from pathlib import Path
import secrets
import tempfile
import time
import unittest
import cv2
import httpx
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
BASE=os.environ.get("TEST_BASE_URL","http://127.0.0.1:8010")

class SystemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from scripts.download_test_asset import ensure
        ensure()
        cls.client=httpx.Client(base_url=BASE,timeout=40)
        cls.other=httpx.Client(base_url=BASE,timeout=40)
        cls.password="Test-"+secrets.token_urlsafe(16)
        cls.email=f"test-{secrets.token_hex(6)}@example.com"
        response=cls.client.post('/api/auth/register',json={"name":"Kiểm thử API","email":cls.email,"password":cls.password})
        assert response.status_code==201,response.text
        cls.uid=response.json()['id']
        other=cls.other.post('/api/auth/register',json={"name":"Người dùng khác","email":f"test-{secrets.token_hex(6)}@example.com","password":cls.password})
        assert other.status_code==201,other.text
        cls.other_uid=other.json()['id']
        cls.client.post('/api/consents',json={"granted":True}).raise_for_status()
        cls.photo=(ROOT/'tests/assets/astronaut.png').read_bytes()

    @classmethod
    def tearDownClass(cls):
        cls.client.delete('/api/users/me/data')
        cls.other.delete('/api/users/me/data')
        cls.client.post('/api/auth/logout');cls.other.post('/api/auth/logout')
        cls.client.close();cls.other.close()

    def analyze(self,content=None,save=False):
        return self.client.post('/api/analysis/image',files={'file':('sample.png',content or self.photo,'image/png')},data={'save':str(save).lower(),'threshold':'.6'})

    def test_health_and_frontend(self):
        response=self.client.get('/api/health');self.assertEqual(response.status_code,200,response.text)
        self.assertTrue(response.json()['mongodb']);self.assertTrue(response.json()['ai']['ready'])
        self.assertIn('Expression Lab',self.client.get('/').text)

    def test_image_real_model_and_no_save(self):
        before=self.client.get('/api/sessions').json()['total']
        response=self.analyze();self.assertEqual(response.status_code,200,response.text)
        data=response.json();self.assertGreaterEqual(len(data['faces']),1)
        face=data['faces'][0];self.assertEqual(len(face['scores']),7)
        self.assertAlmostEqual(sum(face['scores'].values()),1,places=4)
        self.assertIsNone(data['session_id'])
        self.assertEqual(before,self.client.get('/api/sessions').json()['total'])

    def test_save_ownership_feedback_export_delete(self):
        response=self.analyze(save=True);self.assertEqual(response.status_code,200,response.text)
        data=response.json();sid=data['session_id'];self.assertTrue(sid)
        self.assertEqual(self.other.get('/api/sessions/'+sid).status_code,404)
        self.assertEqual(self.other.delete('/api/sessions/'+sid).status_code,404)
        report=self.client.get('/api/sessions/'+sid+'/report');self.assertEqual(report.status_code,200)
        self.assertIn('text/csv',report.headers['content-type']);self.assertIn('timestamp_ms',report.text)
        feedback={'session_id':sid,'frame_index':0,'face_id':data['faces'][0]['face_id'],'suggested_label':'happy'}
        self.assertEqual(self.client.post('/api/feedback',json=feedback).status_code,200)
        self.assertEqual(self.other.post('/api/feedback',json=feedback).status_code,404)
        self.assertEqual(self.client.delete('/api/sessions/'+sid).status_code,200)
        self.assertEqual(self.client.get('/api/sessions/'+sid).status_code,404)

    def test_no_face_has_no_fabricated_label(self):
        out=io.BytesIO();Image.new('RGB',(640,480),'#dddddd').save(out,format='PNG')
        response=self.analyze(out.getvalue());self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['status'],'NO_FACE');self.assertEqual(response.json()['faces'],[])

    def test_multiple_faces(self):
        image=np.asarray(Image.open(io.BytesIO(self.photo)).convert('RGB'))
        combined=np.concatenate([image,image],axis=1)
        out=io.BytesIO();Image.fromarray(combined).save(out,format='PNG')
        response=self.analyze(out.getvalue());self.assertEqual(response.status_code,200,response.text)
        self.assertGreaterEqual(len(response.json()['faces']),2)

    def test_invalid_image_and_threshold(self):
        self.assertEqual(self.analyze(b'not an image').status_code,400)
        response=self.client.post('/api/analysis/image',files={'file':('x.png',self.photo)},data={'threshold':'1.5'})
        self.assertEqual(response.status_code,422)
        out=io.BytesIO();Image.new('RGB',(5000,4100)).save(out,format='PNG')
        self.assertEqual(self.analyze(out.getvalue()).status_code,400)

    def test_consent_required_and_revoke(self):
        self.assertEqual(self.other.post('/api/analysis/image',files={'file':('x.png',self.photo)}).status_code,403)
        self.client.post('/api/consents',json={'granted':False})
        try:self.assertEqual(self.analyze().status_code,403)
        finally:self.client.post('/api/consents',json={'granted':True})

    def test_authentication_rbac_and_origin(self):
        self.assertEqual(httpx.get(BASE+'/api/users/me').status_code,401)
        self.assertEqual(self.client.get('/api/admin/users').status_code,403)
        self.assertEqual(self.client.post('/api/models/missing/activate').status_code,403)
        self.assertEqual(self.client.post('/api/consents',json={'granted':True},headers={'origin':'https://evil.example'}).status_code,403)
        self.assertEqual(self.client.post('/api/auth/register',json={'name':'Duplicate','email':self.email,'password':self.password}).status_code,409)
        self.assertEqual(self.client.post('/api/auth/login',json={'email':self.email,'password':'wrong-password'}).status_code,401)

    def make_video(self,path,seconds=2):
        image=cv2.imdecode(np.frombuffer(self.photo,np.uint8),cv2.IMREAD_COLOR)
        writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'mp4v'),10,(512,512))
        self.assertTrue(writer.isOpened())
        for _ in range(seconds*10):writer.write(image)
        writer.release()

    def poll(self,jid):
        for _ in range(100):
            response=self.client.get('/api/jobs/'+jid);response.raise_for_status();data=response.json()
            if data['status'] not in ('QUEUED','PROCESSING'):return data
            time.sleep(.15)
        self.fail('Video processing timed out')

    def test_video_job_real_inference_and_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'sample.mp4';self.make_video(path)
            response=self.client.post('/api/analysis/video',files={'file':('sample.mp4',path.read_bytes(),'video/mp4')},data={'save':'true'})
            self.assertEqual(response.status_code,202,response.text)
            jid=response.json()['id'];self.assertEqual(self.other.get('/api/jobs/'+jid).status_code,404)
            result=self.poll(jid);self.assertEqual(result['status'],'COMPLETED',result)
            self.assertGreater(result['result']['frame_count'],0);self.assertTrue(result['session_id'])
            times=[f['timestamp_ms'] for f in result['result']['frames']];self.assertEqual(times,sorted(times))
            self.client.delete('/api/sessions/'+result['session_id'])

    def test_video_invalid_content_and_cancel(self):
        bad=self.client.post('/api/analysis/video',files={'file':('broken.mp4',b'invalid bytes','video/mp4')})
        self.assertEqual(bad.status_code,202,bad.text);self.assertEqual(self.poll(bad.json()['id'])['status'],'FAILED')
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'sample.mp4';self.make_video(path,10)
            response=self.client.post('/api/analysis/video',files={'file':('sample.mp4',path.read_bytes(),'video/mp4')})
            self.assertEqual(response.status_code,202,response.text);jid=response.json()['id']
            self.client.post('/api/jobs/'+jid+'/cancel')
            self.assertEqual(self.poll(jid)['status'],'CANCELLED')

    def test_websocket_live_result_stop_and_save(self):
        import websockets
        async def scenario():
            url=BASE.replace('http://','ws://').replace('https://','wss://')+'/ws/analysis/live'
            cookie='expression_session='+self.client.cookies.get('expression_session')
            async with websockets.connect(url,origin=BASE,additional_headers={'Cookie':cookie}) as ws:
                await ws.send(json.dumps({'save':True,'threshold':.6}))
                await ws.send(self.photo)
                result=json.loads(await asyncio.wait_for(ws.recv(),10))
                self.assertEqual(result['type'],'result');self.assertGreaterEqual(len(result['faces']),1)
                await ws.send('stop');stopped=json.loads(await ws.recv())
                self.assertEqual(stopped['type'],'stopped');self.assertTrue(stopped['session_id'])
                self.client.delete('/api/sessions/'+stopped['session_id'])
        asyncio.run(scenario())

    def test_logout_invalidates_server_session(self):
        with httpx.Client(base_url=BASE) as separate:
            login=separate.post('/api/auth/login',json={'email':self.email,'password':self.password});self.assertEqual(login.status_code,200)
            token=separate.cookies.get('expression_session')
            separate.post('/api/auth/logout')
            self.assertEqual(httpx.get(BASE+'/api/users/me',headers={'Cookie':'expression_session='+token}).status_code,401)

if __name__=='__main__':unittest.main()
