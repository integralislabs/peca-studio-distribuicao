"""Private media imports and asynchronous FFmpeg timelines. No shell commands."""
import json, math, re, shutil, subprocess, threading, uuid, sys
from pathlib import Path
from urllib.parse import urlparse, parse_qs

class MediaService:
 def __init__(self,root):
  self.root=Path(root).resolve()/ 'media'; self.root.mkdir(parents=True,exist_ok=True)
  self.lock=threading.RLock(); self.jobs={}; self.procs={}
  self.index=self.root/'index.json'; self.assets=json.loads(self.index.read_text('utf-8')) if self.index.exists() else {}
 def _save(self):
  with self.lock:
   tmp=self.index.with_suffix('.tmp'); tmp.write_text(json.dumps(self.assets,ensure_ascii=False),'utf-8');tmp.replace(self.index)
 def file_path(self,id):
  if not isinstance(id,str) or id not in self.assets: raise ValueError('Mídia não encontrada.')
  p=(self.root/self.assets[id]['file']).resolve()
  if p.parent!=self.root or not p.is_file(): raise ValueError('Arquivo indisponível.')
  return p
 def _probe(self,path):
  try:
   r=subprocess.run([shutil.which('ffprobe') or 'ffprobe','-v','error','-protocol_whitelist','file,pipe,crypto','-show_format','-show_streams','-of','json',str(path)],capture_output=True,timeout=30,check=True)
   d=json.loads(r.stdout); duration=float(d.get('format',{}).get('duration',0)); streams=d.get('streams',[])
   if not 0<duration<=21600 or not any(s.get('codec_type') in ('audio','video') for s in streams):raise ValueError()
   return {'duration':duration,'video':any(s.get('codec_type')=='video' for s in streams),'audio':any(s.get('codec_type')=='audio' for s in streams)}
  except Exception:raise ValueError('Formato de mídia inválido ou FFprobe indisponível.') from None
 def upload(self,raw,filename):
  if not raw or len(raw)>512*1024*1024:raise ValueError('Arquivo vazio ou maior que 512 MB.')
  suffix=Path(str(filename)).suffix.lower()
  if suffix not in ('.mp4','.mov','.mkv','.webm','.mp3','.wav','.m4a','.ogg'):raise ValueError('Extensão de mídia não aceita.')
  id=uuid.uuid4().hex;p=self.root/(id+suffix);p.write_bytes(raw)
  try:meta=self._probe(p)
  except Exception:p.unlink(missing_ok=True);raise
  self.assets[id]={'assetId':id,'name':Path(str(filename).replace('\\','/')).name[:180],'file':p.name,**meta};self._save();return self.assets[id].copy()
 @staticmethod
 def youtube_url(url):
  p=urlparse(str(url));q=parse_qs(p.query)
  if p.scheme!='https' or p.username or p.password or p.port or 'list' in q:raise ValueError('Use uma URL HTTPS de um vídeo YouTube, sem playlist.')
  host=p.hostname; vid=None
  if host=='youtu.be':vid=p.path.strip('/')
  elif host in ('youtube.com','www.youtube.com','m.youtube.com'):
   if p.path=='/watch':vid=q.get('v',[''])[0]
   elif p.path.startswith(('/shorts/','/embed/')):vid=p.path.split('/')[2]
  if not vid or not re.fullmatch(r'[A-Za-z0-9_-]{11}',vid):raise ValueError('URL YouTube inválida.')
  return 'https://www.youtube.com/watch?v='+vid
 @staticmethod
 def ytdlp_command():
  return [sys.executable,'--yt-dlp'] if getattr(sys,'frozen',False) else [sys.executable,'-m','yt_dlp']
 def _youtube(self,d):
  url=self.youtube_url(d.get('url'));tool=self.ytdlp_command();id=uuid.uuid4().hex;out=self.root/(id+'.%(ext)s')
  common=tool+['--ignore-config','--no-playlist','--no-progress','--socket-timeout','20','--max-filesize','512M']
  try:
   meta=subprocess.run(common+['--skip-download','--dump-single-json','--',url],capture_output=True,timeout=120)
   if meta.returncode:raise ValueError()
   info=json.loads(meta.stdout)
  except Exception:raise ValueError('Metadados YouTube indisponíveis. Verifique acesso público e yt-dlp.') from None
  result={'title':info.get('title'),'description':str(info.get('description') or '')[:150000],'url':url,'duration':info.get('duration'),'subtitles':[],'warnings':[],'mediaDownloaded':False}
  diagnostic=meta.stderr.decode('utf-8',errors='replace') if isinstance(meta.stderr,bytes) else str(meta.stderr or '')
  if any(term in diagnostic.lower() for term in ('challenge','javascript','js runtime','remote components')):result['warnings'].append('O YouTube solicitou solução JavaScript; alguns formatos podem estar ausentes. Nenhum componente remoto foi baixado ou executado.')
  (self.root/(id+'.info.json')).write_text(json.dumps(info,ensure_ascii=False),'utf-8')
  try:
   subs=subprocess.run(common+['--skip-download','--write-subs','--write-auto-subs','--sub-langs','pt.*,en.*','--sub-format','srt','--convert-subs','srt','-o',str(out),'--',url],capture_output=True,timeout=120)
   if subs.returncode:
    error=subs.stderr.decode('utf-8',errors='replace') if isinstance(subs.stderr,bytes) else str(subs.stderr or '')
    result['warnings'].append('Legendas parcialmente indisponíveis: limite HTTP 429 do YouTube. Tente novamente mais tarde.' if '429' in error else 'Não foi possível obter todas as legendas. Metadados foram preservados.')
  except Exception:result['warnings'].append('Consulta de legendas não concluída. Metadados foram preservados.')
  for p in self.root.glob(id+'*.srt'):result['subtitles'].append({'language':p.stem[len(id)+1:],'text':p.read_text('utf-8')[:200000]})
  if not result['subtitles'] and not result['warnings']:result['warnings'].append('Nenhuma legenda disponível neste vídeo.')
  if d.get('download') is True:
   try:
    video=subprocess.run(common+['-f','bv*[height<=1080]+ba/b[height<=1080]','--merge-output-format','mp4','-o',str(out),'--',url],capture_output=True,timeout=300)
    candidates=[p for p in self.root.glob(id+'.*') if p.suffix in ('.mp4','.webm','.mkv')]
    if video.returncode or not candidates:raise ValueError()
    p=candidates[0];meta=self._probe(p)
   except Exception:raise ValueError('Download do vídeo não concluído; nenhum vídeo foi importado. Metadados foram consultados, mas o YouTube pode exigir runtime JavaScript/EJS ou limitar o acesso. Não usamos cookies nem componentes remotos.') from None
   self.assets[id]={'assetId':id,'name':str(result['title'])[:180],'file':p.name,**meta};self._save();result['asset']=self.assets[id].copy();result['mediaDownloaded']=True
  return result
 def _render(self,d):
  clips=d.get('clips');w=int(d.get('width',1280));h=int(d.get('height',720))
  if not isinstance(clips,list) or not 1<=len(clips)<=50:raise ValueError('Escolha de 1 a 50 cortes.')
  if w<64 or h<64 or w>1920 or h>1920 or w%2 or h%2:raise ValueError('Dimensões pares entre 64 e 1920.')
  args=[shutil.which('ffmpeg') or 'ffmpeg','-y','-hide_banner','-loglevel','error'];filters=[];total=0
  for i,c in enumerate(clips):
   a=self.assets.get(c.get('assetId'),{});p=self.file_path(c.get('assetId'));start=float(c.get('start',0));end=float(c.get('end',a.get('duration',0)))
   if not a.get('video') or not math.isfinite(start+end) or start<0 or end<=start or end>a['duration']+.05:raise ValueError('Corte fora da duração da mídia.')
   dur=end-start;total+=dur;args+=['-ss',str(start),'-t',str(dur),'-protocol_whitelist','file,pipe,crypto','-i',str(p)]
   filters.append(f'[{i}:v]scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,setpts=PTS-STARTPTS[v{i}]')
   filters.append(f'[{i}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,asetpts=PTS-STARTPTS[a{i}]' if a.get('audio') else f'anullsrc=r=48000:cl=stereo,atrim=duration={dur},asetpts=PTS-STARTPTS[a{i}]')
  if total>21600:raise ValueError('Timeline maior que seis horas.')
  filters.append(''.join(f'[v{i}][a{i}]' for i in range(len(clips)))+f'concat=n={len(clips)}:v=1:a=1[v][a]');v='v';audio='a'
  if d.get('audioId'):
   args+=['-protocol_whitelist','file,pipe,crypto','-i',str(self.file_path(d['audioId']))];audio=f'{len(clips)}:a';filters.append('[a]anullsink')
  job=uuid.uuid4().hex;output=self.root/(job+'.mp4')
  if d.get('srt'):
   srt=str(d['srt'])
   if len(srt)>200000 or '-->' not in srt:raise ValueError('Legenda SRT inválida.')
   (self.root/(job+'.srt')).write_text(srt,'utf-8');filters.append(f'[v]subtitles={job}.srt[sub]');v='sub'
  args+=['-filter_complex',';'.join(filters),'-map',f'[{v}]','-map',f'[{audio}]' if audio=='a' else audio,'-c:v','libx264','-preset','veryfast','-pix_fmt','yuv420p','-c:a','aac','-t',str(total),'-movflags','+faststart','-progress','pipe:1','-nostats',str(output)]
  self.jobs[job]={'jobId':job,'status':'queued','progress':0}
  def run():
   state=self.jobs[job]
   try:
    if state['status']=='cancelled':return
    proc=subprocess.Popen(args,cwd=self.root,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',errors='replace');self.procs[job]=proc;state['status']='rendering'
    for line in proc.stdout:
     if line.startswith('out_time_us='):state['progress']=min(.99,int(line.strip().split('=')[1])/1000000/total)
    err=proc.stderr.read();code=proc.wait()
    if state['status']=='cancelled':output.unlink(missing_ok=True);return
    if code:raise ValueError('FFmpeg não concluiu a renderização: '+err[-600:])
    self.assets[job]={'assetId':job,'name':'timeline.mp4','file':output.name,**self._probe(output)};self._save();state.update(status='done',progress=1,assetId=job)
   except Exception as e:state.update(status='error',error=str(e));output.unlink(missing_ok=True)
   finally:
    proc=self.procs.pop(job,None)
    if proc:
     if proc.poll() is None:proc.kill();proc.wait()
     proc.stdout.close();proc.stderr.close()
  threading.Thread(target=run,daemon=True).start();return self.jobs[job].copy()
 def dispatch(self,action,data=None):
  d=data or {}
  if action=='list':return {'assets':[dict(a) for a in self.assets.values()]}
  if action=='youtube':return self._youtube(d)
  if action=='render':return self._render(d)
  if action in ('status','cancel'):
   j=self.jobs.get(d.get('jobId'))
   if not j:raise ValueError('Renderização não encontrada.')
   if action=='cancel' and j['status'] in ('queued','rendering'):
    j['status']='cancelled';p=self.procs.get(j['jobId'])
    if p:p.terminate()
   return j.copy()
  raise ValueError('Ação de mídia desconhecida.')
