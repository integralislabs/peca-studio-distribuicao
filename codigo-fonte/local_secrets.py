"""Small account-local DPAPI vault; plaintext credentials never touch disk."""
import base64, ctypes, json, os, threading
from ctypes import wintypes
from pathlib import Path

class _Blob(ctypes.Structure):
 _fields_=[('size',wintypes.DWORD),('data',ctypes.POINTER(ctypes.c_byte))]

def _crypt(raw,decrypt=False):
 if os.name!='nt':raise ValueError('O cofre de credenciais requer Windows DPAPI.')
 buf=ctypes.create_string_buffer(raw);src=_Blob(len(raw),ctypes.cast(buf,ctypes.POINTER(ctypes.c_byte)));out=_Blob()
 api=ctypes.windll.crypt32.CryptUnprotectData if decrypt else ctypes.windll.crypt32.CryptProtectData
 if not api(ctypes.byref(src),None,None,None,None,1,ctypes.byref(out)):raise ValueError('Não foi possível acessar o cofre deste usuário Windows.')
 try:return ctypes.string_at(out.data,out.size)
 finally:ctypes.windll.kernel32.LocalFree(out.data)

class SecretStore:
 def __init__(self,root):
  self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True);self.path=self.root/'credentials.dpapi';self.lock=threading.RLock()
 def _read(self):
  return json.loads(_crypt(self.path.read_bytes(),True)) if self.path.exists() else {}
 def _write(self,data):
  tmp=self.path.with_suffix('.tmp');raw=_crypt(json.dumps(data,ensure_ascii=False).encode());fd=os.open(tmp,os.O_CREAT|os.O_TRUNC|os.O_WRONLY,0o600)
  with os.fdopen(fd,'wb') as f:f.write(raw)
  os.replace(tmp,self.path)
 def get(self,name,default=None):
  with self.lock:return self._read().get(name,default)
 def set(self,name,value):
  if not isinstance(name,str) or not 1<=len(name)<=200 or not isinstance(value,str) or len(value)>32768:raise ValueError('Credencial inválida.')
  with self.lock:data=self._read();data[name]=value;self._write(data)
 def delete(self,name):
  with self.lock:data=self._read();data.pop(name,None);self._write(data)
 def status(self,names):
  with self.lock:data=self._read();return {name:bool(data.get(name)) for name in names}
