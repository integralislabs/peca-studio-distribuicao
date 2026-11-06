"""Windows WebView2 host. Mutable state never resides in the application bundle."""
import argparse,json,os,sys,threading,runpy,socket
from pathlib import Path
from http.server import ThreadingHTTPServer
APP_VERSION='1.9.1'
class StrictHTTPServer(ThreadingHTTPServer):
 allow_reuse_address=False
 def server_bind(self):
  if os.name=='nt' and hasattr(socket,'SO_EXCLUSIVEADDRUSE'):self.socket.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
  super().server_bind()
def resource_root():return Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))
def data_root():return Path(os.environ.get('PECA_STUDIO_DATA_ROOT',str(Path(os.environ.get('LOCALAPPDATA',Path.home()/'AppData'/'Local'))/'PecaStudio')))
def prepare_runtime():
 root=resource_root();data=data_root();data.mkdir(parents=True,exist_ok=True)
 os.environ['PECA_STUDIO_DATA_ROOT']=str(data)
 tools=root/'tools'
 if tools.exists():os.environ['PATH']=str(tools)+os.pathsep+str(tools/'tesseract')+os.pathsep+os.environ.get('PATH','')
 if (tools/'tesseract'/'tessdata').exists():os.environ['TESSDATA_PREFIX']=str(tools/'tesseract'/'tessdata')
 return root,data
def diagnose():
 import shutil,importlib.util
 return {'app':'peca-studio','version':APP_VERSION,'frozen':bool(getattr(sys,'frozen',False)),'resourceRoot':str(resource_root()),'dataRoot':str(data_root()),'webview':importlib.util.find_spec('webview') is not None,'ffmpeg':bool(shutil.which('ffmpeg')),'tesseract':bool(shutil.which('tesseract'))}
def main():
 if '--yt-dlp' in sys.argv:
  prepare_runtime();sys.argv.remove('--yt-dlp');runpy.run_module('yt_dlp',run_name='__main__');return 0
 if '--mcp' in sys.argv:
  for stream in (sys.stdin,sys.stdout):
   if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8')
  prepare_runtime();sys.argv.remove('--mcp');runpy.run_module('mcp_server',run_name='__main__');return 0
 parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=17866);parser.add_argument('--serve',action='store_true');parser.add_argument('--diagnose',action='store_true');parser.add_argument('--self-test',action='store_true');parser.add_argument('--gui-self-test',action='store_true');parser.add_argument('--output');args=parser.parse_args()
 root,data=prepare_runtime()
 if args.diagnose or args.self_test:
  result=diagnose()
  if args.self_test:
   from http.server import ThreadingHTTPServer
   import server,urllib.request
   server.ROOT=root
   http=StrictHTTPServer(('127.0.0.1',0),server.Handler);http.local_config_dir=data;http.studio_data_root=data
   thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
   try:
    with urllib.request.urlopen(f'http://127.0.0.1:{http.server_port}/api/health') as response:result['http']=json.load(response)['ok']
   finally:http.shutdown();http.server_close()
  value=json.dumps(result,ensure_ascii=False)
  if args.output:Path(args.output).write_text(value,encoding='utf-8')
  if sys.stdout:print(value)
  return 0 if result['webview'] and (not args.self_test or result.get('http')) else 1
 if os.name=='nt' and getattr(sys,'frozen',False):
  import ctypes
  handle=ctypes.windll.kernel32.GetConsoleWindow()
  if handle:ctypes.windll.user32.ShowWindow(handle,0)
 import server,webview
 from http.server import ThreadingHTTPServer
 server.ROOT=root
 try:http=StrictHTTPServer(('127.0.0.1',args.port),server.Handler)
 except OSError:
  message=f'Não foi possível abrir a porta local {args.port}. Feche outra instância do Peça Studio ou inicie com --port e uma porta livre.'
  if args.output:Path(args.output).write_text(json.dumps({'ok':False,'error':message}),encoding='utf-8')
  if os.name=='nt' and not args.gui_self_test:
   import ctypes
   ctypes.windll.user32.MessageBoxW(None,message,'Peça Studio',16)
  elif sys.stderr:print(message,file=sys.stderr)
  return 2
 http.local_config_dir=data;http.studio_data_root=data
 if args.serve:
  try:http.serve_forever()
  except KeyboardInterrupt:pass
  finally:http.server_close()
  return 0
 thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
 gui_result={'ok':False}
 try:
  window=webview.create_window('Peça Studio 1.9.1',f'http://127.0.0.1:{http.server_port}',width=1440,height=940,min_size=(960,640),hidden=args.gui_self_test)
  if args.gui_self_test:
   def loaded():
    result=diagnose();result['webview2Loaded']=window.evaluate_js('document.title');result['renderer']='edgechromium'
    gui_result['ok']=bool(result['webview2Loaded']);timer.cancel()
    if args.output:Path(args.output).write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
    window.destroy()
   window.events.loaded+=loaded
   timer=threading.Timer(30,window.destroy);timer.daemon=True;timer.start()
  webview.start(gui='edgechromium',private_mode=False,storage_path=str(data/'webview'))
 finally:http.shutdown();http.server_close()
 return 0 if not args.gui_self_test or gui_result['ok'] else 1
if __name__=='__main__':raise SystemExit(main())


