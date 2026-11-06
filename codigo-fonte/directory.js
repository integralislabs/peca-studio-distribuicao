/** Handles stay with the caller in memory; never add them to backups or piece metadata. */
import {packageFiles,packagePath,PACKAGE_MAX_FILES,PACKAGE_MAX_BYTES} from './packages.js';
export async function readDirectoryPackage(handle){
 const files=new Map();let size=0,entries=0;
 async function visit(dir,prefix='',depth=0){
  if(depth>16)throw new Error('Profundidade máxima da pasta: 16.');
  for await(const [name,child] of dir.entries()){
   if(++entries>500)throw new Error('A pasta deve ter até 500 entradas, incluindo subpastas.');
   const path=packagePath(prefix+name);
   if(child.kind==='directory'){await visit(child,path+'/',depth+1);continue;}
   if(child.kind!=='file')continue;
   const file=await child.getFile();size+=file.size;
   if(files.size>=PACKAGE_MAX_FILES||size>PACKAGE_MAX_BYTES)throw new Error('Pasta limitada a 100 arquivos e 100 MB.');files.set(path,file);
  }
 }
 await visit(handle);return files.size?packageFiles(files):files;
}
export async function packageFingerprint(handle){
 const files=await readDirectoryPackage(handle),parts=[];
 for(const [path,file] of [...files].sort(([a],[b])=>a.localeCompare(b))){const digest=await crypto.subtle.digest('SHA-256',await file.arrayBuffer());parts.push(path+':'+Array.from(new Uint8Array(digest),b=>b.toString(16).padStart(2,'0')).join(''));}
 return parts.join('\n');
}
/** Explicit caller action only. Errors propagate (including revoked permission).
 * Browser file writes are sequential, not atomic; caller must report partial write errors.
 * Unrelated files are retained; export only creates/updates named package entries. */
export async function saveDirectoryPackage(handle,entries){
 packageFiles(new Map(entries.map(f=>[f.name,{size:f.bytes.length}])));
 const priority=name=>name==='index.html'?2:name==='peca-studio.json'?1:0;
 const ordered=[...entries].sort((a,b)=>priority(a.name)-priority(b.name));
 for(const {name,bytes} of ordered){const segments=packagePath(name).split('/');let dir=handle;for(const segment of segments.slice(0,-1))dir=await dir.getDirectoryHandle(segment,{create:true});const file=await dir.getFileHandle(segments.at(-1),{create:true}),writer=await file.createWritable();try{await writer.write(bytes);await writer.close();}catch(e){try{await writer.abort();}catch{}throw e;}}
 return packageFingerprint(handle);
}
