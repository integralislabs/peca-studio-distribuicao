"""Explicit fixture origin. NEVER calls OpenAI or uses an actual API key."""
import argparse
import base64
import sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from qa_server import QAHandler
from ai_service import normalize_brief, AIError, public_config

def content(data,key):
    brief=normalize_brief(data)
    if brief['topic']=='ERRO DE QA':raise AIError('Erro simulado de QA: briefing e prévia preservados.',502)
    result = {'model':'fixture-sem-api','draft':{'title':'QA · Plantas para sua casa','caption':'Uma rotina simples ajuda suas plantas. Salve este carrossel. #plantas #cuidados','slides':[{'title':title,'body':body,'imagePrompt':'Fotografia editorial de folhas verdes junto a uma janela iluminada, tons suaves.'} for title,body in [('Verde que cabe na rotina','Comece observando a luz que entra na sua casa.'),('Luz antes de escolher','Conheça a iluminação do ambiente antes de escolher a espécie.'),('Água na medida certa','Confira a umidade do substrato antes de regar.'),('Observe as folhas','Mudanças nas folhas podem indicar que os cuidados precisam de ajuste.'),('Uma rotina para cultivar','Salve estas ideias e acompanhe suas plantas ao longo da semana.')][:brief['count']]]}}
    result['draft']['slides']=(result['draft']['slides']*2)[:brief['count']]
    return result

def image(data,key):
    if 'ERRO DE QA' in data.get('prompt',''):raise AIError('Erro de imagem simulado: textos preservados.',502)
    fixture=Path(__file__).resolve().parent/'fixtures/imagem-teste.jpg'
    return {'src':'data:image/jpeg;base64,'+base64.b64encode(fixture.read_bytes()).decode(),'model':'fixture-sem-api'}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=17866);args=parser.parse_args()
    server=ThreadingHTTPServer(('127.0.0.1',args.port),QAHandler);server.fail_save_once=False
    with patch('server.generate_content',content),patch('server.generate_image',image),patch('server.transcribe_media',lambda blob,filename,key:{'model':'fixture-sem-api','cues':[{'start':0.125,'end':3.5,'text':'Esta é uma transcrição simulada para validar a interface.'}]}),patch('server.public_config',lambda key:{**public_config({'openai':'fixture','claude':'fixture','gemini':'fixture'}),'simulation':True}):
        print(f'SIMULAÇÃO SEM OPENAI: http://127.0.0.1:{args.port}',flush=True)
        server.serve_forever()
