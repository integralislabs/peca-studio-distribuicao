import test from 'node:test';import assert from 'node:assert/strict';import * as ui from '../font-ui.js';
const old={name:'Demo',data:'data:font/ttf;base64,AAEAAAAAAAAAAAAAAAAAAAAAAAA='},next={...old,data:'data:font/ttf;base64,AAEAAAAAAAAAAAAAAAAAAAAAAAE='};
test('font replacement publishes new state before refresh and rolls back conflict',async()=>{
 assert.equal(typeof ui.applyFonts,'function');const state={fonts:[old]};await ui.applyFonts(state,[next],async()=>assert.equal(state.fonts[0].data,next.data));assert.equal(state.fonts[0].data,next.data);
 await assert.rejects(ui.applyFonts(state,[old],async()=>{throw Error('collision');}));assert.equal(state.fonts[0].data,next.data);
});

test('same-name piece fonts prevent replacing bytes and preserve piece embedding',async()=>{
 const state={fonts:[old],pieces:[{fonts:[old]}]};let refresh=false;await assert.rejects(ui.applyFonts(state,[next],async()=>{refresh=true;}),/mesmo nome/);assert.equal(refresh,false);assert.equal(state.fonts[0].data,old.data);assert.equal(state.pieces[0].fonts[0].data,old.data);
});
