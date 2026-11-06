import test from 'node:test';
import assert from 'node:assert/strict';
import {moveToTrash,restoreTrash} from '../trash.js';
import {newPiece,validateState} from '../model.js';
const state=()=>({version:1,projects:[{id:'project',name:'Cliente',color:'#123456',folders:[]}],pieces:[newPiece('project','Arte','feed')]});
test('piece deletion survives backup round trip and restores original IDs',()=>{const s=state(),id=s.pieces[0].id,t=moveToTrash(s,'piece',id);assert.equal(s.pieces.length,1);assert.equal(t.pieces.length,0);const restored=restoreTrash(JSON.parse(JSON.stringify(t)),t.trash[0].id);assert.equal(restored.pieces[0].id,id);assert.equal(restored.trash.length,0);});
test('project deletion retains all pieces and source then restores',()=>{const s=state(),t=moveToTrash(s,'project','project');assert.equal(t.projects.length,0);const r=restoreTrash(t,t.trash[0].id);assert.deepEqual(r.projects,s.projects);assert.deepEqual(r.pieces,s.pieces);});
test('malformed empty trash snapshot is rejected before UI',()=>{assert.throws(()=>validateState({...state(),trash:[{id:'t',kind:'piece',deletedAt:new Date().toISOString(),snapshot:{version:1,projects:[],pieces:[]}}]}));});

