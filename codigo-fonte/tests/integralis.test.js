import test from 'node:test';
import assert from 'node:assert/strict';
test('account UI distinguishes development from commercial access',async()=>{
 const {accountLabel}=await import('../integralis-ui.js');
 assert.match(accountLabel({mode:'development',allowed:true}),/desenvolvimento/);
 assert.match(accountLabel({mode:'commercial',configured:false}),/configuração/);
 assert.match(accountLabel({mode:'commercial',configured:true,allowed:false}),/não confirmado/);
 assert.match(accountLabel({mode:'commercial',configured:true,allowed:true}),/confirmado/);
});
