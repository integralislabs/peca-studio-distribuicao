import argparse,hashlib,json,os,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def validate_build_mode(installer_only,commercial_config):
 if installer_only and commercial_config:raise ValueError('Pacote comercial exige compilar novamente; installer-only não valida o marcador comercial.')
def main():
 p=argparse.ArgumentParser();p.add_argument('--build-root',required=True);p.add_argument('--output',required=True);p.add_argument('--commercial-config');p.add_argument('--installer-only',action='store_true');p.add_argument('--incremental',action='store_true');a=p.parse_args();build=Path(a.build_root).resolve();out=Path(a.output).resolve();build.mkdir(parents=True,exist_ok=True);out.mkdir(parents=True,exist_ok=True)
 validate_build_mode(a.installer_only,a.commercial_config)
 command=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onedir','--console','--name','PecaStudio','--distpath',str(build/'dist'),'--workpath',str(build/'pyinstaller'),'--specpath',str(build),'--paths',str(ROOT),'--collect-all','webview']
 if a.incremental:command.remove('--clean')
 if a.commercial_config:
  config_file=Path(a.commercial_config).resolve();config=json.loads(config_file.read_text('utf-8'))
  if config.get('mode')!='commercial' or not config.get('client_id') or not config.get('product') or config.get('issuer')!='https://integralislabs.com/api/oidc':raise ValueError('Cadastro comercial real e emissor Integralis são obrigatórios; não há fallback de desenvolvimento.')
  if not config.get('updates',{}).get('manifest_url'):raise ValueError('Configure o canal HTTPS final para clientes; não distribua acesso ao GitHub privado.')
  staged=build/'commercial';staged.mkdir(exist_ok=True);(staged/'integralis-config.json').write_text(json.dumps(config),encoding='utf-8')
  (staged/'peca_commercial_build.py').write_text('COMMERCIAL = True\n',encoding='utf-8')
  command+=['--paths',str(staged),'--hidden-import','peca_commercial_build']
  command+=['--add-data',str(staged/'integralis-config.json')+os.pathsep+'.']
 command+=['--collect-submodules','jwt','--collect-all','cryptography']
 command+=['--icon',str(ROOT/'brand'/'integralis-icon.ico')]
 command+=['--version-file',str(ROOT/'packaging'/'windows-version.txt')]
 command+=['--collect-submodules','fontTools','--collect-data','fontTools','--collect-data','svglib','--collect-submodules','yt_dlp','--collect-data','yt_dlp']
 for name in ('server','mcp_server','local_api','PIL','PIL.ImageCms','cv2','reportlab','pypdf','svglib','yt_dlp','yt_dlp.__main__','local_secrets'):command+=['--hidden-import',name]
 for path in sorted(ROOT.iterdir()):
  if path.is_file() and (path.suffix in ('.js','.css') or path.name=='index.html'):command+=['--add-data',str(path)+os.pathsep+'.']
 command+=['--add-data',str(ROOT/'brand')+os.pathsep+'brand']
 tools=build/'tools';tools.mkdir(exist_ok=True)
 for name in ('ffmpeg','ffprobe'):
  binary=shutil.which(name)
  if not binary:raise RuntimeError(name+' ausente')
  shutil.copy2(binary,tools/(name+'.exe'))
 tess=Path('C:/Program Files/Tesseract-OCR');target=tools/'tesseract';target.mkdir(exist_ok=True)
 for path in [tess/'tesseract.exe',*tess.glob('*.dll')]:shutil.copy2(path,target/path.name)
 (target/'tessdata').mkdir(exist_ok=True)
 shutil.copytree(tess/'tessdata'/'configs',target/'tessdata'/'configs',dirs_exist_ok=True)
 for name in ('eng','por','osd'):shutil.copy2(tess/'tessdata'/(name+'.traineddata'),target/'tessdata'/(name+'.traineddata'))
 shutil.copytree(ROOT/'packaging'/'licenses',tools/'licenses',dirs_exist_ok=True)
 python_license=Path(sys.base_prefix)/'LICENSE.txt'
 if python_license.is_file():shutil.copy2(python_license,tools/'licenses'/'Python-LICENSE.txt')
 for info in (ROOT/'.runtime'/'Lib'/'site-packages').glob('*.dist-info'):
  for path in info.rglob('*'):
   if path.is_file() and any(word in path.name.upper() for word in ('LICENSE','COPYING','NOTICE')):
    target=tools/'licenses'/'python'/info.name/path.relative_to(info);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
 command+=['--add-data',str(tools)+os.pathsep+'tools',str(ROOT/'desktop_app.py')]
 if a.installer_only:shutil.copytree(tools,build/'dist'/'PecaStudio'/'_internal'/'tools',dirs_exist_ok=True)
 else:subprocess.run(command,check=True,cwd=ROOT)
 iscc=Path(os.environ['LOCALAPPDATA'])/'Programs'/'Inno Setup 6'/'ISCC.exe'
 subprocess.run([str(iscc),'/DBuildDir='+str(build/'dist'),'/O'+str(out),str(ROOT/'packaging'/'installer.iss')],check=True)
 installer=out/'PecaStudio-Setup-1.9.1.exe'
 with installer.open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
 (out/'release-manifest.json').write_text(json.dumps({'version':'1.9.1','installer':installer.name,'sha256':sha},indent=2)+'\n',encoding='utf-8')
if __name__=='__main__':main()
