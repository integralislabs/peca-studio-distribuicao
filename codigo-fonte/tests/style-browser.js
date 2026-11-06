import {newPiece} from '../model.js';
const results=[];function check(value,label){if(!value)throw new Error(label);results.push(label);}
try{
 const {initStyleUI}=await import('../style-ui.js');
 let piece=newPiece('project','Teste','feed',2),history=[];
 const explicit=newPiece('project','Peça da biblioteca');
 const ui=initStyleUI({getPiece:id=>id===explicit.id?explicit:piece,getSlideIndex:()=>1,projects:()=>[{id:'project',name:'Projeto',folders:[]}],onApply:next=>{history.push(piece);piece={...next,updatedAt:new Date().toISOString()};}});
 document.querySelector('#piece-style').click();
 check(document.querySelector('#style-dialog').open,'abre Estilo');
 const form=document.querySelector('#style-form');form.elements.bg.value='#224466';form.elements.scope.value='current';form.requestSubmit();
 await new Promise(resolve=>setTimeout(resolve,100));
 check(piece.slides[1].bg==='#224466'&&piece.slides[0].bg!=='#224466','aplica somente slide atual');
 check(history.length===1,'operação única disponível para desfazer');
 form.elements.bg.value='#335577';form.requestSubmit();await new Promise(resolve=>setTimeout(resolve,50));check(piece.slides[1].bg==='#335577','segunda aplicação aceita carimbo updatedAt do app');
 piece=history.pop();check(piece.slides[1].bg==='#224466','callback permite desfazer');
 document.querySelector('#style-dialog').close();document.querySelector('#piece-reference').click();
 check(document.querySelector('#reference-dialog').open,'abre Ref. IA');
 const text=document.querySelector('#reference-text');check(text.value.includes('Teste')&&text.value.includes('Slide 2'),'referência completa');text.value='Minha instrução';check(!text.readOnly,'referência editável');
 document.querySelector('#reference-dialog').close();ui.openReference(explicit.id);check(text.value.includes('Peça da biblioteca'),'referência usa ID explícito da biblioteca');
 ui.destroy();check(!document.querySelector('#reference-dialog'),'remove diálogos e listeners');
 document.querySelector('#results').textContent='PASS '+results.length+'\n'+results.join('\n');document.title='PASS Estilo';
}catch(e){document.querySelector('#results').textContent='FAIL '+e.stack;document.title='FAIL Estilo';}
