import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
import ai_service as ai
from test_ai import BRIEF,DRAFT

class TranscriptionTests(unittest.TestCase):
    def test_no_key_or_wrong_media_never_calls_provider(self):
        for blob,name,key in [(b'abc','video.mp4',''),(b'abc','bad.exe','key'),(b'','empty.wav','key'),(b'x'*25_000_001,'large.mp4','key')]:
            with patch.object(ai,'urlopen') as call,self.assertRaises(ai.AIError):ai.transcribe_media(blob,name,key)
            call.assert_not_called()
    def test_multipart_and_segment_timestamps(self):
        raw={'text':'Uma ideia.','segments':[{'start':17.06,'end':18.05,'text':'Uma ideia.'}]}
        with patch.object(ai,'urlopen',return_value=io.BytesIO(json.dumps(raw).encode())) as call:
            result=ai.transcribe_media(b'media-fixture','local.mp4','test-key')
            req=call.call_args.args[0];self.assertEqual(req.full_url,'https://api.openai.com/v1/audio/transcriptions');self.assertIn(b'whisper-1',req.data);self.assertIn(b'verbose_json',req.data);self.assertIn(b'name="file"; filename="upload.mp4"',req.data)
            self.assertEqual(result['cues'][0]['start'],17.06);self.assertNotIn('test-key',json.dumps(result))
    def test_provider_error_and_bad_segments_preserve_contract(self):
        with patch.object(ai,'urlopen',side_effect=HTTPError('x',401,'test-secret',{},io.BytesIO(b'test-secret'))) as call:
            with self.assertRaises(ai.AIError) as caught:ai.transcribe_media(b'abc','a.wav','test-secret')
            self.assertNotIn('test-secret',str(caught.exception));self.assertEqual(call.call_count,1)
        for raw in [{'text':'X','segments':[{'start':5,'end':2,'text':'X'}]},{'text':'','segments':[]}]:
            with patch.object(ai,'urlopen',return_value=io.BytesIO(json.dumps(raw).encode())),self.assertRaises(ai.AIError):ai.transcribe_media(b'abc','a.wav','key')
    def test_source_context_bounded_and_present_in_request(self):
        source=dict(id='source1',title='Vídeo',url='https://www.youtube.com/watch?v=3FEjcVt0VtM',start=17,end=22,text='Informação de origem.')
        raw={'status':'completed','output':[{'content':[{'type':'output_text','text':json.dumps(DRAFT)}]}]}
        with patch.object(ai,'urlopen',return_value=io.BytesIO(json.dumps(raw).encode())) as call:
            ai.generate_content({**BRIEF,'source':source,'kind':'short'},'key');body=json.loads(call.call_args.args[0].data);self.assertIn('Informação de origem.',body['input']);self.assertIn('roteiro',body['instructions'].lower())
        with patch.object(ai,'urlopen') as call,self.assertRaises(ai.AIError):ai.generate_content({**BRIEF,'source':{**source,'text':'x'*10001}},'key')
        call.assert_not_called()

if __name__=='__main__':unittest.main()
