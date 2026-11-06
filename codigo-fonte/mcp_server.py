"""MCP JSON-lines stdio; stdout is reserved exclusively for JSON-RPC."""
import argparse
import json
from pathlib import Path
import sys
import urllib.request
import urllib.parse
from workspace_service import StudioService, TOOLS

PROPERTIES={
 'expectedRevision':{'type':'integer','minimum':0},'operationId':{'type':'string','maxLength':200},
 'piece':{'type':'object','description':'Complete app composition: title/channel/format/status/slides, with slide width/height/bg/bgImage/layers and optional portable fonts. Replace is integral: include metadata to retain.'},'folderId':{'type':['string','null']},
 'projectId':{'type':'string'},'pieceId':{'type':'string'},'slideId':{'type':'string'},'layerId':{'type':'string'},
 'name':{'type':'string','maxLength':120},'title':{'type':'string','maxLength':180},'color':{'type':'string'},
 'image':{'type':['string','null']},'count':{'type':'integer','minimum':1,'maximum':30},
 'width':{'type':'integer','minimum':100,'maximum':4096},'height':{'type':'integer','minimum':100,'maximum':4096},
 'html':{'type':'string','maxLength':20000000},'controls':{'type':'object','additionalProperties':{'type':'number'}},
 'texts':{'type':'object','additionalProperties':{'type':'string'}},'options':{'type':'object'},'format':{'type':'string'}}
FIELDS={
 'pieces_create_html':(['projectId','title','folderId','html'],['projectId','html']),
 'pieces_get_html':(['pieceId'],['pieceId']),
 'pieces_list_editables':(['pieceId'],['pieceId']),
 'pieces_update_html':(['pieceId','texts','controls'],['pieceId']),
 'collections_export':(['projectId','format','options'],['projectId']),
 'projects_list':([],[]),'projects_create':(['name','color'],['name']),
 'pieces_list':(['projectId'],[]),'pieces_get':(['pieceId'],['pieceId']),
 'pieces_import':(['projectId','piece','folderId'],['projectId','piece']),
 'pieces_replace':(['pieceId','piece'],['pieceId','piece']),
 'pieces_create':(['projectId','title','format','count'],['projectId']),
 'pieces_update_texts':(['pieceId','slideId','texts'],['pieceId','texts']),
 'pieces_set_image':(['pieceId','slideId','layerId','image'],['pieceId','image']),
 'pieces_set_background':(['pieceId','slideId','color','image'],['pieceId']),
 'pieces_resize':(['pieceId','slideId','width','height'],['pieceId','width','height']),
 'pieces_export':(['pieceId','format','options'],['pieceId'])}
def tools_list():
    result=[]
    for name in TOOLS:
        fields,required=FIELDS[name]; fields=list(fields); required=list(required)
        readonly=name in ('projects_list','pieces_list','pieces_get','pieces_get_html','pieces_list_editables')
        if not readonly: fields+=['expectedRevision','operationId']; required+=['expectedRevision']
        result.append({'name':name,'description':name.replace('_',' ')+(' (requer revisão atual)' if not readonly else ''),'inputSchema':{'type':'object','properties':{f:PROPERTIES[f] for f in fields},'required':required,'additionalProperties':False},'annotations':{'readOnlyHint':readonly,'destructiveHint':False,'openWorldHint':False}})
    return result

class Bridge:
    def __init__(self,url,token_file):
        u=urllib.parse.urlsplit(url)
        if u.scheme!='http' or u.hostname not in ('127.0.0.1','localhost','::1') or u.username or u.password: raise ValueError('Bridge requires loopback HTTP URL')
        self.url=url.rstrip('/')+'/api/local/mcp'; self.token_file=Path(token_file)
    def dispatch(self,name,arguments):
        token=self.token_file.read_text('utf-8').strip()
        if not token or '\n' in token or '\r' in token: raise ValueError('Invalid local token file')
        request=urllib.request.Request(self.url,data=json.dumps({'name':name,'arguments':arguments}).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+token},method='POST')
        # Explicitly disable proxies and redirects: tokens must stay on loopback.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self,*args,**kwargs): return None
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
        with opener.open(request,timeout=30) as response: return json.load(response)

def handle(message,service):
    ident=message.get('id'); method=message.get('method')
    if 'id' not in message: return None
    response={'jsonrpc':'2.0','id':ident}
    try:
        if message.get('jsonrpc')!='2.0': raise ValueError('Invalid JSON-RPC version')
        if method=='initialize': result={'protocolVersion':'2024-11-05','capabilities':{'tools':{'listChanged':False}},'serverInfo':{'name':'peca-studio-local','version':'1.9.1'}}
        elif method=='ping': result={}
        elif method=='tools/list': result={'tools':tools_list()}
        elif method=='tools/call':
            params=message.get('params',{}); name=params['name']; arguments=params.get('arguments',{})
            try:
                canonical=name[7:] if isinstance(name,str) and name.startswith('studio_') else name
                schema=next(t['inputSchema'] for t in tools_list() if t['name']==canonical)
                if not isinstance(arguments,dict) or set(arguments)-set(schema['properties']) or any(k not in arguments for k in schema['required']): raise ValueError('Invalid tool arguments')
                value=service.dispatch(name,arguments)
                result={'content':[{'type':'text','text':json.dumps(value,ensure_ascii=False)}],'isError':False}
            except Exception as exc:
                result={'content':[{'type':'text','text':str(exc) if isinstance(exc,(ValueError,KeyError,StopIteration)) else 'Local service unavailable'}],'isError':True}
        else:
            response['error']={'code':-32601,'message':'Method not found'}; return response
        response['result']=result
    except Exception:
        response['error']={'code':-32602,'message':'Invalid request parameters'}
    return response

def main():
    parser=argparse.ArgumentParser(description=__doc__); group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--workspace',help='Explicit opt-in folder (standalone mode)'); group.add_argument('--url',help='Running local Peça Studio base URL')
    parser.add_argument('--token-file'); args=parser.parse_args()
    if args.url and not args.token_file: parser.error('--url requires --token-file')
    if not args.url:
        import os,sys
        root=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))
        from integralis_auth import installation_config
        if installation_config(root).get('mode')=='commercial':
            # Commercial tools must pass the running app's live account/session gate.
            data=Path(os.environ.get('PECA_STUDIO_DATA_ROOT',str(Path(os.environ.get('LOCALAPPDATA',Path.home()/'AppData'/'Local'))/'PecaStudio')))
            service=Bridge('http://127.0.0.1:17866',data/'mcp-token-17866.txt')
        else:service=StudioService(args.workspace)
    else:service=Bridge(args.url,args.token_file)
    for line in sys.stdin:
        if len(line)>150_000_000: response={'jsonrpc':'2.0','id':None,'error':{'code':-32600,'message':'Request too large'}}
        else:
            try:
                message=json.loads(line)
                response=handle(message,service) if isinstance(message,dict) else {'jsonrpc':'2.0','id':None,'error':{'code':-32600,'message':'Invalid request'}}
            except json.JSONDecodeError: response={'jsonrpc':'2.0','id':None,'error':{'code':-32700,'message':'Parse error'}}
        if response is not None: print(json.dumps(response,ensure_ascii=False),flush=True)

if __name__=='__main__': main()
