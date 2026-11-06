import {readFont,loadFonts,fontNames,fontKey} from './fonts.js';
import {FONTS} from './model.js';
/** Publish only a coherent font collection; restore bytes if refresh fails. */
export async function applyFonts(state,fonts,onChange){
 const prior=state.fonts,entries=[...fonts,...(state.pieces||[]).flatMap(p=>p.fonts||[]),...(state.templates||[]).flatMap(t=>t.snapshot?.fonts||[])],map=new Map();
 for(const f of entries){const key=fontKey(f.name);if(map.has(key)&&map.get(key).data!==f.data)throw Error('Há duas fontes diferentes com o mesmo nome. Renomeie uma antes de substituir.');map.set(key,f);}
 const previousNames=[...FONTS];state.fonts=fonts;
 try{const names=await loadFonts([...map.values()]);await onChange?.(fonts);FONTS.splice(0,FONTS.length,...names);}
 catch(error){state.fonts=prior;await loadFonts([...(prior||[]),...(state.pieces||[]).flatMap(p=>p.fonts||[]),...(state.templates||[]).flatMap(t=>t.snapshot?.fonts||[])]);FONTS.splice(0,FONTS.length,...previousNames);throw error;}
}
export function initFontsUI({getState,onChange,onRefresh}){
 const button=document.querySelector('#fonts-button'),dialog=document.querySelector('#fonts-dialog'),list=document.querySelector('#font-list');if(!button||!dialog||!list)return;
 const add=document.createElement('button');add.type='button';add.textContent='Adicionar fontes locais';add.className='primary';
 const status=document.createElement('p');status.setAttribute('role','status');status.setAttribute('aria-live','polite');
 const picker=document.createElement('input');picker.type='file';picker.accept='.ttf,.otf,.woff,.woff2';picker.multiple=true;picker.hidden=true;
 list.before(add,picker,status);
 const refresh=()=>{const fonts=getState().fonts||[];list.replaceChildren();for(const font of fontNames(fonts)){const row=document.createElement('div');row.style.fontFamily=font;row.textContent='Uma ideia ganha forma.';const label=document.createElement('small');label.textContent=font+(fonts.some(f=>f.name===font)?' · incorporada localmente':' · fonte básica do sistema');row.append(label);list.append(row);}status.textContent=fonts.length?`${fonts.length} fonte(s) local(is) incorporada(s).`:'Nenhuma fonte local cadastrada. Adicione TTF, OTF, WOFF ou WOFF2 (até 5 MB cada).';};
 button.addEventListener('click',()=>{try{refresh();dialog.showModal();}catch(e){status.textContent=e.message;}});
 add.addEventListener('click',()=>picker.click());
 picker.onchange=async()=>{add.disabled=true;status.textContent='Verificando fontes locais…';try{const state=getState(),fonts=[...(state.fonts||[])];for(const file of picker.files){const font=await readFont(file),i=fonts.findIndex(x=>fontKey(x.name)===fontKey(font.name));if(i>=0)fonts[i]=font;else fonts.push(font);}await applyFonts(state,fonts,onChange);refresh();onRefresh?.();}catch(e){status.textContent=e.message;}finally{add.disabled=false;picker.value='';}};
}
