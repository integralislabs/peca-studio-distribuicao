import base64
import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from test_ai import BRIEF,DRAFT
import ai_service as ai

class ProviderTests(unittest.TestCase):
    def response(self,value):return io.BytesIO(json.dumps(value).encode())
    def test_claude_contract(self):
        raw={'stop_reason':'end_turn','content':[{'type':'text','text':json.dumps(DRAFT)}]}
        with patch.object(ai,'urlopen',return_value=self.response(raw)) as call:
            result=ai.generate_content({**BRIEF,'provider':'claude'},'claude-key')
            req=call.call_args.args[0];body=json.loads(req.data)
            self.assertEqual(req.full_url,'https://api.anthropic.com/v1/messages')
            self.assertEqual(req.get_header('X-api-key'),'claude-key')
            self.assertIsNone(req.get_header('Authorization'))
            self.assertEqual(body['output_config']['format']['type'],'json_schema')
            self.assertEqual(result['provider'],'claude');self.assertEqual(result['draft'],DRAFT)
    def test_gemini_contract(self):
        raw={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps(DRAFT)}]}}]}
        with patch.object(ai,'urlopen',return_value=self.response(raw)) as call:
            result=ai.generate_content({**BRIEF,'provider':'gemini'},'gemini-key')
            req=call.call_args.args[0];body=json.loads(req.data)
            self.assertTrue(req.full_url.startswith('https://generativelanguage.googleapis.com/v1beta/models/'))
            self.assertNotIn('gemini-key',req.full_url)
            self.assertEqual(req.get_header('X-goog-api-key'),'gemini-key')
            self.assertEqual(body['generationConfig']['responseFormat']['text']['mimeType'],'application/json')
            self.assertEqual(result['draft'],DRAFT);self.assertEqual(result['provider'],'gemini')
    def test_refusals_and_truncated_responses_not_accepted(self):
        for provider,raw in [('claude',{'stop_reason':'max_tokens','content':[]}),('claude',{'stop_reason':'refusal','content':[]}),('gemini',{'promptFeedback':{'blockReason':'SAFETY'}}),('gemini',{'candidates':[{'finishReason':'MAX_TOKENS','content':{'parts':[{'text':json.dumps(DRAFT)}]}}]})]:
            with patch.object(ai,'urlopen',return_value=self.response(raw)),self.assertRaises(ai.AIError):ai.generate_content({**BRIEF,'provider':provider},'key')
    def test_gemini_png_image_and_single_candidate(self):
        png=base64.b64encode(b'\x89PNG\r\n\x1a\nfixture').decode()
        raw={'candidates':[{'finishReason':'STOP','content':{'parts':[{'inlineData':{'mimeType':'image/png','data':png}}]}}]}
        with patch.object(ai,'urlopen',return_value=self.response(raw)) as call:
            result=ai.generate_image({'provider':'gemini','prompt':'Folhas verdes','format':'feed'},'gemini-key')
            self.assertTrue(result['src'].startswith('data:image/png;base64,'))
            self.assertEqual(json.loads(call.call_args.args[0].data)['generationConfig']['candidateCount'],1)
    def test_unknown_provider_and_claude_image_never_call_transport(self):
        for provider in ['evil','Claude',{},None]:
            with patch.object(ai,'urlopen') as call,self.assertRaises(ai.AIError):
                ai.generate_content({**BRIEF,'provider':provider},'key')
            call.assert_not_called()
        with patch.object(ai,'urlopen') as call,self.assertRaises(ai.AIError):ai.generate_image({'provider':'claude','prompt':'Folhas','format':'feed'},'key')
        call.assert_not_called()
    def test_config_has_independent_flags_and_no_keys(self):
        cfg=ai.public_config({'openai':'secret-open','claude':'secret-ant','gemini':''})
        self.assertTrue(cfg['providers']['claude']['configured']);self.assertFalse(cfg['providers']['gemini']['configured'])
        self.assertNotIn('secret-',json.dumps(cfg));self.assertIsNone(cfg['providers']['claude']['imageModel'])
    def test_provider_error_does_not_expose_secret_or_retry(self):
        for provider in ['claude','gemini']:
            with patch.object(ai,'urlopen',side_effect=HTTPError('x',403,'key-secret',{},io.BytesIO(b'key-secret'))) as call:
                with self.assertRaises(ai.AIError) as caught:ai.generate_content({**BRIEF,'provider':provider},'key-secret')
                self.assertNotIn('key-secret',str(caught.exception));self.assertEqual(call.call_count,1)

if __name__=='__main__':unittest.main()
