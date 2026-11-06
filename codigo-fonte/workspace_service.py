"""Opt-in local workspace. No networking, AI calls, or implicit migration."""
import base64
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import threading
import time
import uuid
import unicodedata
from urllib.parse import urlsplit, parse_qs
from contextlib import contextmanager

class ConflictError(ValueError):
    """Caller must reload and reconcile; never overwrite silently."""

_LOCKS={}
_LOCKS_GUARD=threading.Lock()
def _json(value): return json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False,separators=(',',':'))
def _uid(): return str(uuid.uuid4())
def _now(): return time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())

BASE_FONTS=['Arial','Georgia','Trebuchet MS','Verdana','Impact','Courier New']
MAX_ENVELOPE=100_000_000

def validate_fonts(fonts):
    if not isinstance(fonts,list) or len(fonts)>32: raise ValueError('Invalid fonts')
    names=set(); total=0
    for f in fonts:
        name=f.get('name') if isinstance(f,dict) else None
        if not isinstance(name,str) or not 1<=len(name)<=80 or not name[0].isalnum() or any(not (c.isalnum() or c in ' _-') for c in name) or name in BASE_FONTS or name in names: raise ValueError('Invalid font name')
        names.add(name)
        match=re.fullmatch(r'data:font/(ttf|otf|woff|woff2);base64,([A-Za-z0-9+/]+={0,2})',f.get('data',''))
        if not match or len(match[2])%4 or len(match[2])>5*1024*1024*4/3+4: raise ValueError('Invalid font data')
        try: raw=base64.b64decode(match[2],validate=True)
        except Exception as exc: raise ValueError('Invalid font encoding') from exc
        total+=len(raw)
        if len(raw)<12 or raw[:4]!={'ttf':b'\x00\x01\x00\x00','otf':b'OTTO','woff':b'wOFF','woff2':b'wOF2'}[match[1]] or total>20*1024*1024: raise ValueError('Invalid font signature/size')
    return names

def validate_state(data):
    if not isinstance(data,dict) or data.get('version')!=1: raise ValueError('Invalid state version')
    projects,pieces=data.get('projects'),data.get('pieces')
    if not isinstance(projects,list) or not isinstance(pieces,list) or len(projects)>500 or len(pieces)>5000: raise ValueError('Invalid library limits')
    state_fonts=validate_fonts(data.get('fonts',[]))
    ids=set()
    def identifier(obj):
        value=obj.get('id') if isinstance(obj,dict) else None
        if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',value) or value in ids: raise ValueError('Invalid or duplicate id')
        ids.add(value); return value
    def string(value,limit):
        if not isinstance(value,str) or len(value)>limit: raise ValueError('Invalid text')
    def number(value,lo,hi):
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not lo<=value<=hi: raise ValueError('Invalid geometry')
    def color(value):
        if not isinstance(value,str) or not re.fullmatch('#[a-fA-F0-9]{6}',value): raise ValueError('Invalid color')
    def image(value):
        if not isinstance(value,str) or len(value)>8_000_000 or not re.fullmatch(r'data:image/(png|jpeg|webp);base64,[A-Za-z0-9+/=\s]+',value): raise ValueError('Invalid image')
        try: base64.b64decode(value.split(',',1)[1],validate=True)
        except Exception as exc: raise ValueError('Invalid image encoding') from exc
    def youtube(value):
        if value=='': return
        if not isinstance(value,str) or len(value)>600: raise ValueError('Invalid YouTube URL')
        u=urlsplit(value)
        if u.scheme!='https' or u.username or u.password or u.port: raise ValueError('Invalid YouTube URL')
        ident=None
        if u.hostname in ('youtu.be','www.youtu.be'): ident=u.path[1:]
        elif u.hostname in ('youtube.com','www.youtube.com','m.youtube.com'):
            if u.path=='/watch': ident=parse_qs(u.query).get('v',[None])[0]
            else:
                m=re.fullmatch(r'/(shorts|embed)/([^/]+)',u.path)
                if m: ident=m[2]
        if not isinstance(ident,str) or not re.fullmatch(r'[A-Za-z0-9_-]{11}',ident): raise ValueError('Invalid YouTube URL')
    def reference(ref):
        if not isinstance(ref,dict) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',str(ref.get('id',''))): raise ValueError('Invalid reference')
        for key,limit in [('title',180),('text',10000)]:
            string(ref.get(key),limit)
            if not ref[key].strip(): raise ValueError('Empty reference')
        youtube(ref.get('url'))
        if ref.get('start') is not None or ref.get('end') is not None:
            number(ref.get('start'),0,86400); number(ref.get('end'),ref['start'],86400)
    project_ids=set(); folders={}
    for p in projects:
        project_ids.add(identifier(p)); string(p.get('name'),120); color(p.get('color'))
        if 'brandKit' in p:
            kit=p['brandKit']
            if not isinstance(kit,dict): raise ValueError('Invalid brand kit')
            for key,limit in [('name',120),('signature',160),('tone',300)]: string(kit.get(key),limit)
            for key in ('bg','accent','text'): color(kit.get(key))
            if kit.get('titleFont') not in BASE_FONTS+list(state_fonts) or kit.get('bodyFont') not in BASE_FONTS+list(state_fonts): raise ValueError('Unknown brand font')
            if kit.get('logo') is not None:
                logo=kit['logo']; image(logo.get('src'))
                if len(logo['src'])>1500000: raise ValueError('Logo too large')
                number(logo.get('width'),1,2200); number(logo.get('height'),1,2200)
        if not isinstance(p.get('folders'),list) or len(p['folders'])>500: raise ValueError('Invalid folders')
        for f in p['folders']: folders[identifier(f)]=p['id']; string(f.get('name'),120)
    for p in pieces:
        identifier(p); string(p.get('title'),180)
        allowed_fonts=set(BASE_FONTS)|state_fonts|validate_fonts(p.get('fonts',[]))
        for key,limit in [('angle',160),('versionLabel',64),('caption',4000)]:
            if key in p: string(p[key],limit)
        for key in ('variationGroupId','parentPieceId'):
            if key in p and (not isinstance(p[key],str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',p[key])): raise ValueError('Invalid relation id')
        if 'source' in p: reference(p['source'])
        if 'htmlDocument' in p:
            from html_document import validate_document
            validate_document(p['htmlDocument'])
        if 'contentKind' in p and p['contentKind'] not in ('post','carousel','short'): raise ValueError('Invalid content kind')
        if p.get('projectId') not in project_ids or (p.get('folderId') and folders.get(p['folderId'])!=p['projectId']): raise ValueError('Unknown project/folder')
        if p.get('format') not in ('feed','story','quadrado') or p.get('status') not in ('Rascunho','Em edição','Em revisão','Pronto','Publicado') or p.get('channel') not in ('Instagram','YouTube','LinkedIn','Outro'): raise ValueError('Invalid piece metadata')
        if not isinstance(p.get('slides'),list) or not 1<=len(p['slides'])<=30: raise ValueError('Invalid slides')
        for s in p['slides']:
            identifier(s); number(s.get('width'),100,4096); number(s.get('height'),100,4096); color(s.get('bg'))
            if s.get('bgImage'): image(s['bgImage'])
            if not isinstance(s.get('layers'),list) or len(s['layers'])>100: raise ValueError('Invalid layers')
            for l in s['layers']:
                identifier(l); string(l.get('name'),120)
                if 'radius' in l: number(l['radius'],0,4096)
                if 'opacity' in l: number(l['opacity'],0,1)
                if 'rotation' in l:number(l['rotation'],-360,360)
                if type(l.get('visible')) is not bool: raise ValueError('Invalid visibility')
                for key,lo,hi in [('x',-8192,8192),('y',-8192,8192),('w',1,8192)]: number(l.get(key),lo,hi)
                if l.get('type')=='text':
                    if l.get('font') not in allowed_fonts: raise ValueError('Unknown font')
                    string(l.get('text'),10000); string(l.get('font'),120); number(l.get('size'),8,400); color(l.get('color')); number(l.get('lineHeight'),.6,3); number(l.get('letterSpacing'),-10,60)
                    if l.get('align') not in ('left','center','right') or any(type(l.get(k)) is not bool for k in ('bold','italic','underline')): raise ValueError('Invalid text style')
                elif l.get('type')=='image':
                    image(l.get('src')); number(l.get('h'),1,8192); number(l.get('zoom'),.2,5); number(l.get('offsetX'),-4096,4096); number(l.get('offsetY'),-4096,4096)
                    if type(l.get('flip')) is not bool: raise ValueError('Invalid flip')
                elif l.get('type')=='shape':
                    number(l.get('h'),1,8192)
                    if l.get('shape') not in ('rect','ellipse'):raise ValueError('Invalid shape')
                    for key in ('fill','stroke'):
                        if l.get(key) is not None:color(l[key])
                    number(l.get('strokeWidth',0),0,100)
                    if l.get('gradient') is not None:
                        g=l['gradient'];number(g.get('angle'),-360,360);stops=g.get('stops')
                        if not isinstance(stops,list) or not 2<=len(stops)<=16:raise ValueError('Invalid gradient')
                        previous=-1
                        for stop in stops:
                            number(stop.get('offset'),0,1);color(stop.get('color'))
                            if stop['offset']<previous:raise ValueError('Unordered gradient')
                            previous=stop['offset']
                elif l.get('type')=='vector':
                    from vector_pdf import sanitize_svg
                    number(l.get('h'),1,8192);sanitize_svg(l.get('svg'))
                else: raise ValueError('Invalid layer type')
    if 'templates' in data:
        templates=data['templates']
        if not isinstance(templates,list) or len(templates)>200: raise ValueError('Invalid templates')
        for t in templates:
            identifier(t); string(t.get('name'),120)
            if not t['name'].strip() or not isinstance(t.get('snapshot'),dict): raise ValueError('Invalid template')
            snap=t['snapshot']; validate_state({'version':1,'projects':[{'id':snap.get('projectId'),'name':'Modelo','color':'#123456','folders':[]}],'pieces':[{**snap,'folderId':None}]})
    if 'sources' in data:
        sources=data['sources']
        if not isinstance(sources,list) or len(sources)>100: raise ValueError('Invalid sources')
        for source in sources:
            identifier(source); string(source.get('title'),180)
            if not source['title'].strip() or source.get('projectId') not in project_ids: raise ValueError('Invalid source')
            youtube(source.get('url')); cues=source.get('cues')
            if not isinstance(cues,list) or not 1<=len(cues)<=5000: raise ValueError('Invalid cues')
            untimed=cues[0].get('start') is None; total=0; last=-1
            for c in cues:
                string(c.get('text'),3000); total+=len(c['text'])
                if not c['text'].strip() or total>150000: raise ValueError('Invalid cue text')
                if untimed:
                    if c.get('start') is not None or c.get('end') is not None: raise ValueError('Mixed cue timing')
                else:
                    number(c.get('start'),max(0,last),86400); number(c.get('end'),c['start'],86400); last=c['start']
    if 'trash' in data:
        if not isinstance(data['trash'],list) or len(data['trash'])>500:raise ValueError('Invalid trash')
        for entry in data['trash']:
            identifier(entry)
            if entry.get('kind') not in ('piece','project') or not isinstance(entry.get('snapshot'),dict) or 'trash' in entry['snapshot']:raise ValueError('Invalid trash entry')
            string(entry.get('deletedAt'),40)
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}T[0-9:.]+Z',entry['deletedAt']):raise ValueError('Invalid deletion date')
            validate_state(entry['snapshot'])
            if len(entry['snapshot']['projects'])!=1 or entry['kind']=='piece' and len(entry['snapshot']['pieces'])!=1:raise ValueError('Invalid trash snapshot')
    if len(_json(data).encode())>100_000_000: raise ValueError('Workspace exceeds 100 MB')
    return data

class WorkspaceStore:
    def __init__(self,root):
        self.root=Path(root).expanduser().resolve(); self.root.mkdir(parents=True,exist_ok=True)
        self.path=self.asset_path('workspace.json')
        with _LOCKS_GUARD: self._lock=_LOCKS.setdefault(str(self.root),threading.RLock())
    def asset_path(self,name):
        p=(self.root/name).resolve()
        if p==self.root or self.root not in p.parents: raise ValueError('Path outside workspace')
        return p
    @contextmanager
    def locked(self):
        with self._lock:
            lock=self.asset_path('.write.lock'); deadline=time.monotonic()+10
            while True:
                try: fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600); break
                except FileExistsError:
                    if time.monotonic()>deadline: raise ConflictError('Workspace busy; inspect stale .write.lock if process crashed')
                    time.sleep(.02)
            try: yield
            finally: os.close(fd); lock.unlink(missing_ok=True)
    def _read(self):
        if not self.path.exists(): return {'revision':0,'data':{'version':1,'projects':[],'pieces':[]},'_receipts':{}}
        value=json.loads(self.path.read_text('utf-8')); validate_state(value['data']); return value
    def read(self):
        with self._lock:
            value=self._read(); return {'revision':value['revision'],'data':value['data']}
    def _atomic(self,path,value):
        path=self.asset_path(str(path.relative_to(self.root))); path.parent.mkdir(parents=True,exist_ok=True)
        tmp=path.with_name(path.name+'.'+_uid()+'.tmp')
        try:
            with open(tmp,'x',encoding='utf-8') as f: f.write(_json(value)); f.flush(); os.fsync(f.fileno())
            os.replace(tmp,path)
        finally: tmp.unlink(missing_ok=True)
    def _operation(self,old,operationId):
        if not operationId: return None
        if not isinstance(operationId,str) or not 1<=len(operationId)<=200: raise ValueError('Invalid operationId')
        receipt=old.get('_receipts',{}).get(operationId)
        if receipt: return receipt
        digest=hashlib.sha256(operationId.encode()).hexdigest()
        tombstones=old.get('_expiredOperations',[])
        if digest in tombstones: raise ConflictError('operationId expired; reconcile before a new operation')
        if len(tombstones)>=65536: raise ConflictError('Idempotency ledger capacity reached; archive workspace before new operation IDs')
        return None
    def _response(self,old,receipt):
        if 'resultRef' not in receipt: return {'revision':receipt['revision']}
        ref=receipt['resultRef']
        result=next((item for item in old['data'].get(ref['collection'],[]) if item['id']==ref['id']),None)
        if result is None: raise ConflictError('Operation resource no longer exists; reconcile')
        return {'revision':old['revision'],'result':copy.deepcopy(result)}
    def _commit(self,old,data,operationId=None,fingerprint=None,result=None):
        validate_state(data)
        receipts=copy.deepcopy(old.get('_receipts',{})); expired=list(old.get('_expiredOperations',[]))
        envelope={'revision':old['revision']+1,'data':data}
        if operationId:
            self._operation(old,operationId)
            receipt={'fingerprint':fingerprint,'revision':envelope['revision']}
            if result is not None:
                value=result['result']
                collection='exportJobs' if 'pieceId' in value and 'status' in value and 'piece' in value else ('pieces' if 'slides' in value else 'projects')
                receipt['resultRef']={'collection':collection,'id':value['id']}
            receipts[operationId]=receipt
        # insertion order is explicitly persisted separately; JSON is key-sorted.
        order=[key for key in old.get('_receiptOrder',list(receipts)) if key in receipts]
        if operationId and operationId not in order: order.append(operationId)
        while len(receipts)>512 or len(_json(receipts).encode())>1_000_000:
            key=order.pop(0); receipts.pop(key,None); expired.append(hashlib.sha256(key.encode()).hexdigest())
        if len(expired)>65536: raise ConflictError('Idempotency ledger capacity reached')
        value={**envelope,'_receipts':receipts,'_receiptOrder':order,'_expiredOperations':expired}
        if len(_json(value).encode())>MAX_ENVELOPE: raise ValueError('Workspace envelope exceeds 100 MB including receipts')
        if old['revision']: self._atomic(self.asset_path(f"backups/revision-{old['revision']}.json"),old)
        previous={p['id']:p for p in old['data']['pieces']}
        for piece in data['pieces']:
            if previous.get(piece['id'])!=piece: self._atomic(self.asset_path('pieces/'+piece['id']+'.json'),piece)
        self._atomic(self.path,value)
        backups=sorted(self.asset_path('backups').glob('revision-*.json'),key=lambda p:int(p.stem.split('-')[1])) if self.asset_path('backups').exists() else []
        for path in backups[:-20]:
            try: self.asset_path(str(path.relative_to(self.root))).unlink(missing_ok=True)
            except OSError: pass  # canonical commit already succeeded; retry pruning next save
        return {'revision':envelope['revision']}
    def write(self,data,expectedRevision,operationId=None):
        fingerprint=hashlib.sha256(_json(data).encode()).hexdigest()
        with self.locked():
            old=self._read(); receipt=self._operation(old,operationId)
            if receipt:
                if receipt['fingerprint']!=fingerprint: raise ConflictError('operationId reused with different input')
                return self._response(old,receipt)
            if type(expectedRevision) is not int or expectedRevision!=old['revision']: raise ConflictError('Workspace revision changed')
            return self._commit(old,copy.deepcopy(data),operationId,fingerprint)

TOOLS=['pieces_create_html','pieces_get_html','pieces_list_editables','pieces_update_html','collections_export','projects_list','projects_create','pieces_list','pieces_get','pieces_create','pieces_import','pieces_replace','pieces_update_texts','pieces_set_image','pieces_set_background','pieces_resize','pieces_export']
class StudioService:
    def __init__(self,root): self.store=WorkspaceStore(root); self.root=self.store.root
    def dispatch(self,name,arguments=None):
        a=copy.deepcopy(arguments or {})
        if name.startswith('studio_'): name=name[7:]
        if name not in TOOLS: raise ValueError('Unknown tool')
        with self.store.locked():
            old=self.store._read(); data=copy.deepcopy(old['data']); revision=old['revision']
            if name=='projects_list': return {'revision':revision,'result':data['projects']}
            if name=='pieces_list': return {'revision':revision,'result':[p for p in data['pieces'] if not a.get('projectId') or p['projectId']==a['projectId']]}
            if name=='pieces_get': return {'revision':revision,'result':self._piece(data,a)}
            if name in ('pieces_get_html','pieces_list_editables'):
                document=self._piece(data,a).get('htmlDocument')
                if not document:raise ValueError('Piece has no preserved HTML document')
                return {'revision':revision,'result':document if name=='pieces_get_html' else {k:document[k] for k in ('editables','controls')}}
            fingerprint=hashlib.sha256(_json({'name':name,'arguments':{k:v for k,v in a.items() if k not in ('expectedRevision','operationId')}}).encode()).hexdigest()
            receipt=self.store._operation(old,a.get('operationId'))
            if receipt:
                if receipt['fingerprint']!=fingerprint: raise ConflictError('operationId reused with different input')
                return self.store._response(old,receipt)
            if type(a.get('expectedRevision')) is not int or a['expectedRevision']!=revision: raise ConflictError('expectedRevision required/current revision changed')
            if name=='projects_create':
                result={'id':_uid(),'name':a['name'],'color':a.get('color','#6750a4'),'folders':[]}; data['projects'].append(result)
            elif name=='pieces_create_html':
                from html_document import prepare_document,render_document
                doc=prepare_document(a.get('html'))
                result={'id':_uid(),'projectId':a['projectId'],'folderId':a.get('folderId'),'title':a.get('title','HTML preservado'),'channel':'Instagram','format':'feed','status':'Rascunho','updatedAt':_now(),'htmlDocument':doc,'slides':[{'id':_uid(),'width':f['width'],'height':f['height'],'bg':'#ffffff','bgImage':None,'layers':[]} for f in doc['frames']]}
                for i,slide in enumerate(result['slides']):slide['bgImage']='data:image/png;base64,'+base64.b64encode(render_document(doc,'png',i)[0]).decode()
                data['pieces'].append(result)
            elif name=='collections_export':
                if a.get('format','png') not in ('png','jpeg','pdf'):raise ValueError('Invalid export format')
                pieces=[p for p in data['pieces'] if p['projectId']==a['projectId']]
                if not pieces:raise ValueError('Collection is empty or unknown')
                if len(pieces)+sum(j.get('status')=='pending' for j in data.get('exportJobs',[]))>32:raise ValueError('Export queue limited to 32 pending jobs')
                result=[]
                for piece in pieces:
                    from image_quality import assert_image_quality
                    assert_image_quality(piece)
                    snapshot=copy.deepcopy(piece)
                    fonts={f['name']:f for f in data.get('fonts',[])+snapshot.get('fonts',[])}
                    snapshot['fonts']=list(fonts.values())
                    result.append({'id':_uid(),'pieceId':piece['id'],'piece':snapshot,'format':a.get('format','png'),'options':a.get('options',{}),'status':'pending','createdAt':_now()})
                data.setdefault('exportJobs',[]).extend(result)
            elif name in ('pieces_import','pieces_replace'):
                if not isinstance(a.get('piece'),dict): raise ValueError('piece must be a complete composition object')
                result=copy.deepcopy(a['piece'])
                if name=='pieces_import':
                    result['id']=_uid(); result['projectId']=a['projectId']; result['folderId']=a.get('folderId')
                    if not isinstance(result.get('slides'),list): raise ValueError('Invalid imported slides')
                    for slide in result['slides']:
                        if not isinstance(slide,dict) or not isinstance(slide.get('layers'),list): raise ValueError('Invalid imported slide')
                        slide['id']=_uid()
                        for layer in slide['layers']:
                            if not isinstance(layer,dict): raise ValueError('Invalid imported layer')
                            layer['id']=_uid()
                    data['pieces'].append(result)
                else:
                    target=self._piece(data,a)
                    # Composition replacement cannot move the target into another project/folder.
                    result.update(id=target['id'],projectId=target['projectId'],folderId=target.get('folderId'))
                    data['pieces'][data['pieces'].index(target)]=result
                result['updatedAt']=_now()
                # _commit validates the complete destination state before any file is changed.
            elif name=='pieces_create':
                fmt=a.get('format','feed'); w,h={'feed':(1080,1350),'story':(1080,1920),'quadrado':(1080,1080)}[fmt]
                count=a.get('count',1)
                if type(count) is not int or not 1<=count<=30: raise ValueError('count must be 1..30')
                result={'id':_uid(),'projectId':a['projectId'],'folderId':None,'title':a.get('title','Sem título'),'channel':'Instagram','format':fmt,'status':'Rascunho','updatedAt':_now(),'slides':[]}
                for _ in range(count): result['slides'].append({'id':_uid(),'width':w,'height':h,'bg':'#151020','bgImage':None,'layers':[{'id':_uid(),'type':'text','name':'Título','text':'Uma nova ideia.','x':90,'y':550,'w':900,'font':'Arial','size':64,'color':'#ffffff','bold':True,'italic':False,'underline':False,'align':'left','lineHeight':1.15,'letterSpacing':0,'visible':True}]})
                data['pieces'].append(result)
            else:
                result=self._piece(data,a); result['updatedAt']=_now()
                slides=[s for s in result['slides'] if not a.get('slideId') or s['id']==a['slideId']]
                if not slides: raise ValueError('Unknown slide')
                if result.get('htmlDocument') and name not in ('pieces_update_html','pieces_export'):raise ValueError('Use pieces_update_html for preserved HTML; Canvas mutations would diverge from the source')
                if name=='pieces_update_html':
                    from html_document import update_document,render_document
                    result['htmlDocument']=update_document(result.get('htmlDocument'),a.get('texts'),a.get('controls'))
                    for i,slide in enumerate(result['slides']):slide['bgImage']='data:image/png;base64,'+base64.b64encode(render_document(result['htmlDocument'],'png',i)[0]).decode();slide['layers']=[]
                elif name=='pieces_update_texts':
                    texts=a['texts']; found=set()
                    for s in slides:
                        for l in s['layers']:
                            if l['id'] in texts and l['type']=='text': l['text']=texts[l['id']]; found.add(l['id'])
                    if found!=set(texts): raise ValueError('Unknown text layer')
                elif name=='pieces_set_background':
                    for s in slides:
                        if 'color' in a: s['bg']=a['color']
                        if 'image' in a: s['bgImage']=a['image']
                elif name=='pieces_set_image':
                    found=False
                    for s in slides:
                        for l in s['layers']:
                            if l['id']==a.get('layerId') and l['type']=='image': l['src']=a['image']; found=True
                    if not found and a.get('layerId'): raise ValueError('Unknown image layer')
                    if not a.get('layerId'):
                        for s in slides: s['layers'].append({'id':_uid(),'type':'image','name':'Imagem','src':a['image'],'x':0,'y':0,'w':s['width'],'h':s['height'],'zoom':1,'offsetX':0,'offsetY':0,'flip':False,'visible':True})
                elif name=='pieces_resize':
                    for s in slides:
                        sx=a['width']/s['width']; sy=a['height']/s['height']
                        for l in s['layers']:
                            for key in ('x','w'): l[key]*=sx
                            l['y']*=sy
                            if l['type']=='image': l['h']*=sy
                            else: l['size']*=min(sx,sy)
                        s['width']=a['width']; s['height']=a['height']
                elif name=='pieces_export':
                    from image_quality import assert_image_quality
                    assert_image_quality(result)
                    if a.get('format','png') not in ('png','jpeg','pdf'): raise ValueError('Invalid export format')
                    if sum(j.get('status')=='pending' for j in data.get('exportJobs',[]))>=32:raise ValueError('Export queue limited to 32 pending jobs')
                    snapshot=copy.deepcopy(result);font_map={}
                    key=lambda name:unicodedata.normalize('NFKC',name).lower()
                    used={key(l['font']) for slide in snapshot['slides'] for l in slide['layers'] if l['type']=='text'}
                    for font in data.get('fonts',[])+snapshot.get('fonts',[]):
                        name=key(font['name'])
                        if name in font_map and font_map[name]['data']!=font['data']:raise ValueError('Font collision: '+font['name'])
                        font_map[name]=font
                    snapshot['fonts']=copy.deepcopy([font for name,font in font_map.items() if name in used])
                    result={'id':_uid(),'pieceId':result['id'],'piece':snapshot,'format':a.get('format','png'),'options':a.get('options',{}),'status':'pending','createdAt':_now()}
                    data.setdefault('exportJobs',[]).append(result)
            response={'revision':revision+1,'result':result}
            self.store._commit(old,data,a.get('operationId'),fingerprint,response)
            return response
    def _piece(self,data,a):
        for p in data['pieces']:
            if p['id']==a.get('pieceId'): return p
        raise ValueError('Unknown piece')
    def pending_exports(self): return [j for j in self.store.read()['data'].get('exportJobs',[]) if j['status']=='pending']
    def complete_export(self,jobId,data):
        """Complete idempotently. Retain 256 completed metadata records, never delete export files.
        Pending snapshots are bounded to 32; completed records discard embedded piece/font data.
        """
        with self.store.locked():
            old=self.store._read(); state=copy.deepcopy(old['data'])
            job=next((j for j in state.get('exportJobs',[]) if j['id']==jobId),None)
            if not job: raise ValueError('Unknown export job')
            if job['status']=='complete': return {'revision':old['revision'],'result':job}
            encoded=data['base64']
            if len(encoded)>140_000_000: raise ValueError('Export too large')
            raw=base64.b64decode(encoded,validate=True)
            expected={'png':('image/png',b'\x89PNG\r\n\x1a\n'),'jpeg':('image/jpeg',b'\xff\xd8\xff'),'pdf':('application/pdf',b'%PDF-')}[job['format']]
            if data.get('mime')!=expected[0] or not raw.startswith(expected[1]): raise ValueError('Invalid export file')
            path=self.store.asset_path('exports/'+jobId+'.'+job['format']); path.parent.mkdir(exist_ok=True)
            tmp=path.with_suffix('.tmp'); tmp.write_bytes(raw); os.replace(tmp,path)
            job.update(status='complete',path=str(path.relative_to(self.root)),mime=expected[0],sha256=hashlib.sha256(raw).hexdigest())
            job.pop('piece',None)
            completed=[j for j in state.get('exportJobs',[]) if j.get('status')=='complete']
            keep={j['id'] for j in completed[-256:]}
            state['exportJobs']=[j for j in state.get('exportJobs',[]) if j.get('status')!='complete' or j['id'] in keep]
            self.store._commit(old,state)
            return {'revision':old['revision']+1,'result':job}
