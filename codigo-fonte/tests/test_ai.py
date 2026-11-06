import base64
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ai_service as ai

BRIEF = dict(topic='Como cuidar de plantas', audience='Iniciantes', goal='Ensinar', tone='Didático', brand='Botânica', style='editorial', format='feed', count=2, bg='#171322', accent='#b8e38b')
DRAFT = dict(title='Plantas em casa', caption='Salve para consultar.', slides=[dict(title='Comece com luz', body='Observe a janela.', imagePrompt='Planta ao lado de uma janela'), dict(title='Cuide sem excessos', body='Confira a umidade.', imagePrompt='Detalhe de folhas verdes')])

class AIServiceTests(unittest.TestCase):
    def test_brief_rejects_out_of_bounds_and_bool(self):
        for count in (0,11,True,1.5,'2'):
            with self.subTest(count=count), self.assertRaises(ai.AIError): ai.normalize_brief({**BRIEF,'count':count})
        for field,value in [('topic',''),('format','bad'),('bg','red'),('style','script')]:
            with self.subTest(field=field), self.assertRaises(ai.AIError): ai.normalize_brief({**BRIEF,field:value})

    def test_missing_key_makes_no_request(self):
        with patch.object(ai,'urlopen') as call:
            with self.assertRaises(ai.AIError): ai.generate_content(BRIEF,'')
            call.assert_not_called()

    def test_content_request_and_validated_response(self):
        raw=dict(status='completed',output=[dict(type='message',content=[dict(type='output_text',text=json.dumps(DRAFT))])],usage={'input_tokens':12,'output_tokens':24})
        with patch.object(ai,'urlopen',return_value=io.BytesIO(json.dumps(raw).encode())) as call:
            result=ai.generate_content(BRIEF,'test-key')
            req=call.call_args.args[0]; body=json.loads(req.data)
            self.assertEqual(req.full_url,'https://api.openai.com/v1/responses')
            self.assertFalse(body['store']); self.assertTrue(body['text']['format']['strict'])
            self.assertEqual(result['draft'],DRAFT)
            self.assertNotIn('test-key',json.dumps(result))

    def test_refusal_incomplete_and_wrong_count_rejected(self):
        for raw in [dict(status='incomplete'),dict(status='completed',output=[dict(content=[dict(type='refusal')])]),dict(status='completed',output=[dict(content=[dict(type='output_text',text=json.dumps({**DRAFT,'slides':[]}))])])]:
            with patch.object(ai,'urlopen',return_value=io.BytesIO(json.dumps(raw).encode())),self.assertRaises(ai.AIError): ai.generate_content(BRIEF,'test-key')

    def test_provider_errors_sanitized_no_retry(self):
        for err in [HTTPError('x',401,'x',{},io.BytesIO(b'test-secret')),HTTPError('x',429,'x',{},io.BytesIO(b'test-secret')),URLError('test-secret'),TimeoutError('test-secret')]:
            with patch.object(ai,'urlopen',side_effect=err) as call:
                with self.assertRaises(ai.AIError) as caught: ai.generate_content(BRIEF,'test-secret')
                self.assertNotIn('test-secret',str(caught.exception));self.assertEqual(call.call_count,1)

    def test_image_one_jpeg_and_no_url_download(self):
        jpeg=b'\xff\xd8\xff'+b'example'
        with patch.object(ai,'urlopen',return_value=io.BytesIO(json.dumps({'data':[{'b64_json':base64.b64encode(jpeg).decode()}]}).encode())) as call:
            result=ai.generate_image({'prompt':'Uma planta bonita','format':'feed'},'test-key')
            body=json.loads(call.call_args.args[0].data)
            self.assertEqual(body['n'],1);self.assertEqual(body['output_format'],'jpeg')
            self.assertTrue(result['src'].startswith('data:image/jpeg;base64,'))
        for data in ({'data':[{'url':'https://untrusted.example/file'}]},{'data':[{'b64_json':'bad'}]}):
            with patch.object(ai,'urlopen',return_value=io.BytesIO(json.dumps(data).encode())),self.assertRaises(ai.AIError): ai.generate_image({'prompt':'Uma planta','format':'feed'},'test-key')

    def test_config_never_contains_key(self):
        self.assertNotIn('secret',json.dumps(ai.public_config('secret')))
        self.assertTrue(ai.public_config('secret')['configured'])

if __name__ == '__main__': unittest.main()
