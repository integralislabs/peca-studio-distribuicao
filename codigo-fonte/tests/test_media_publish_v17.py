import unittest,tempfile,subprocess,shutil,time,json,datetime as dt
from pathlib import Path
from media_service import MediaService
from publishing_service import PublicationService,OfficialAdapter
class Secrets:
 def __init__(self):self.items={}
 def get(self,k):return self.items.get(k)
 def set(self,k,v):self.items[k]=v
 def delete(self,k):self.items.pop(k,None)
class Adapter:
 def __init__(self,fail=False):self.calls=[];self.fail=fail
 def validate(self,a,t):return {'items':[{'id':a['target']}]}
 def publish(self,a,t,j,m):
  self.calls.append(j['id'])
  if self.fail:raise TimeoutError()
  return {'id':'fixture-only'}
class Contracts(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
 def tearDown(self):self.tmp.cleanup()
 def test_youtube_subtitle_429_preserves_metadata(self):
  from unittest.mock import patch
  import subprocess
  m=MediaService(self.root)
  metadata={'title':'Fixture public video','duration':30,'description':'Public fixture description'}
  def run(args,**kwargs):
   if '--dump-single-json' in args:return subprocess.CompletedProcess(args,0,json.dumps(metadata).encode(),b'')
   return subprocess.CompletedProcess(args,1,b'',b'HTTP Error 429: Too Many Requests')
  with patch('media_service.subprocess.run',side_effect=run):result=m._youtube({'url':'https://youtu.be/abcdefghijk','download':False})
  self.assertEqual(result['title'],metadata['title']);self.assertEqual(result['description'],metadata['description']);self.assertEqual(result['subtitles'],[]);self.assertTrue(result['warnings']);self.assertFalse(result['mediaDownloaded'])
 def test_youtube_download_failure_is_not_successful_import(self):
  from unittest.mock import patch
  import subprocess
  m=MediaService(self.root)
  def run(args,**kwargs):return subprocess.CompletedProcess(args,0,json.dumps({'title':'Fixture','duration':10}).encode(),b'') if '--dump-single-json' in args else subprocess.CompletedProcess(args,1,b'',b'Unavailable')
  with patch('media_service.subprocess.run',side_effect=run):
   with self.assertRaises(ValueError):m._youtube({'url':'https://youtu.be/abcdefghijk','download':True})
 def test_ytdlp_frozen_dispatch(self):
  from unittest.mock import patch
  import sys
  with patch.object(sys,'frozen',True,create=True):self.assertEqual(MediaService.ytdlp_command(),[sys.executable,'--yt-dlp'])
 def test_ytdlp_source_dispatch(self):
  import sys
  self.assertEqual(MediaService.ytdlp_command(),[sys.executable,'-m','yt_dlp'])
 def test_youtube_allowlist(self):
  self.assertEqual(MediaService.youtube_url('https://youtu.be/abcdefghijk'),'https://www.youtube.com/watch?v=abcdefghijk')
  for url in ['https://evil.com/watch?v=abcdefghijk','https://youtube.com.evil.com/watch?v=abcdefghijk','https://youtube.com/watch?v=abcdefghijk&list=123','https://youtube.com@evil.com/watch?v=abcdefghijk']:
   with self.assertRaises(ValueError):MediaService.youtube_url(url)
 def test_confined_file_and_bad_upload(self):
  m=MediaService(self.root)
  for id in ['../../x','C:/Windows/win.ini',None]:
   with self.assertRaises(ValueError):m.file_path(id)
  with self.assertRaises(ValueError):m.upload(b'invalid','test.mp4')
  self.assertFalse(list(m.root.glob('*.mp4')))
 def test_real_render_cuts_reorder_audio_subtitles(self):
  if not shutil.which('ffmpeg'):self.skipTest('FFmpeg unavailable')
  source=self.root/'fixture.mp4';audio=self.root/'audio.wav'
  subprocess.run(['ffmpeg','-y','-v','error','-f','lavfi','-i','color=c=red:s=160x120:r=30:d=1','-f','lavfi','-i','sine=frequency=440:duration=1','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-shortest',str(source)],check=True)
  subprocess.run(['ffmpeg','-y','-v','error','-f','lavfi','-i','sine=frequency=800:duration=1',str(audio)],check=True)
  m=MediaService(self.root);a=m.upload(source.read_bytes(),'fixture.mp4');b=m.upload(audio.read_bytes(),'audio.wav')
  j=m.dispatch('render',{'clips':[{'assetId':a['assetId'],'start':.5,'end':.9},{'assetId':a['assetId'],'start':0,'end':.4}],'width':160,'height':120,'audioId':b['assetId'],'srt':'1\n00:00:00,000 --> 00:00:00,700\nTeste de legenda\n'})
  for _ in range(100):
   result=m.dispatch('status',{'jobId':j['jobId']})
   if result['status'] in ('done','error'):break
   time.sleep(.1)
  self.assertEqual(result['status'],'done',result)
  probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(m.file_path(result['assetId']))]))
  self.assertEqual([s['codec_name'] for s in probe['streams']],['h264','aac']);self.assertAlmostEqual(float(probe['format']['duration']),.8,delta=.1)
 def _queue(self,adapter):
  secrets=Secrets();p=PublicationService(self.root,secrets,adapter);a=p.dispatch('connect',{'provider':'youtube','target':'testchannel','token':'fixture-token'})
  args={'accountId':a['id'],'when':(dt.datetime.now(dt.timezone.utc)-dt.timedelta(minutes=1)).isoformat(),'payload':{'title':'Fixture only','assetId':'fixture'}}
  j=p.dispatch('schedule',args);self.assertEqual(p.dispatch('schedule',args)['id'],j['id']);return p,j
 def test_disabled_draft_and_idempotency(self):
  a=Adapter();p,j=self._queue(a);p.run_due();self.assertEqual(a.calls,[])
  p.dispatch('confirm',{'id':j['id'],'approved':True,'target':'testchannel'});p.run_due();self.assertEqual(a.calls,[])
  p.state['enabled']=True;p.run_due();p.run_due();self.assertEqual(len(a.calls),1);self.assertEqual(p.dispatch('status')['queue'][0]['status'],'published')
  self.assertNotIn('fixture-token',p.path.read_text())
 def test_unknown_never_retries_and_restart_disables(self):
  a=Adapter(True);p,j=self._queue(a);p.dispatch('confirm',{'id':j['id'],'approved':True,'target':'testchannel'});p.state['enabled']=True;p.run_due();p.run_due();self.assertEqual(len(a.calls),1);self.assertEqual(p.state['queue'][0]['status'],'unknown')
  p2=PublicationService(self.root,p.secrets,a);self.assertFalse(p2.state['enabled'])
 def test_requires_timezone_and_target_confirmation(self):
  p,j=self._queue(Adapter())
  with self.assertRaises(ValueError):p.dispatch('confirm',{'id':j['id'],'approved':True,'target':'wrong'})
  with self.assertRaises(ValueError):p.dispatch('schedule',{'accountId':j['accountId'],'when':'2026-11-05T10:00','payload':j['payload']})
 def test_youtube_official_http_contract(self):
  class HTTPFixture(OfficialAdapter):
   def __init__(self):self.calls=[]
   def request(self,method,url,token,body=None,headers=None):
    self.calls.append((method,url,body,headers))
    return {'headers':{'Location':'https://www.googleapis.com/upload/youtube/v3/videos?upload_id=fixture'},'data':{'items':[{'id':'fixture-channel'}]} if method=='GET' else {'id':'fixture'}}
  f=self.root/'fixture.mp4';f.write_bytes(b'fixture-only')
  class Media:
   def file_path(self,id):return f
  adapter=HTTPFixture();adapter.publish({'provider':'youtube','target':'fixture-channel'},'fixture-token',{'payload':{'assetId':'x','title':'Fixture'}},Media())
  self.assertEqual([x[0] for x in adapter.calls],['GET','POST','PUT']);self.assertIn('uploadType=resumable',adapter.calls[1][1]);self.assertEqual(adapter.calls[2][3]['Content-Range'],'bytes 0-11/12')
 def test_youtube_refuses_wrong_channel_before_upload(self):
  class WrongIdentity(OfficialAdapter):
   def validate(self,a,t):return {'items':[{'id':'other-channel'}]}
   def request(self,*args):raise AssertionError('No upload may start')
  with self.assertRaises(ValueError):WrongIdentity().publish({'provider':'youtube','target':'wanted'},'fixture',{'payload':{}},None)
 def test_token_newline_rejected(self):
  p=PublicationService(self.root,Secrets(),Adapter())
  with self.assertRaises(ValueError):p.dispatch('connect',{'provider':'youtube','target':'id','token':'bad\r\nheader'})
 def test_render_rejects_nan(self):
  m=MediaService(self.root)
  with self.assertRaises(ValueError):m.dispatch('render',{'clips':[]})
 def test_reject_arbitrary_payload_fields(self):
  p,j=self._queue(Adapter())
  with self.assertRaises(ValueError):p.dispatch('schedule',{'accountId':j['accountId'],'when':j['when'],'payload':{'title':'ok','assetId':'fixture','access_token':'accidental-secret'}})
if __name__=='__main__':unittest.main()
