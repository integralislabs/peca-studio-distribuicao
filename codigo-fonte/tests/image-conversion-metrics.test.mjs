import test from 'node:test';
import assert from 'node:assert/strict';
import {comparePixels} from '../visual-qa.js';
test('métricas conhecidas: idêntico e diferença RGB absoluta',()=>{
 assert.deepEqual(comparePixels(new Uint8ClampedArray([0,10,20,255]),new Uint8ClampedArray([0,10,20,255])),{meanAbsoluteError:0,pixelsWithin20:1,pixelCount:1});
 assert.deepEqual(comparePixels(new Uint8ClampedArray([0,0,0,255,100,100,100,255]),new Uint8ClampedArray([30,30,30,255,110,110,110,255])),{meanAbsoluteError:20,pixelsWithin20:0.5,pixelCount:2});
});
test('métricas rejeitam buffers incompatíveis',()=>{assert.throws(()=>comparePixels(new Uint8ClampedArray(4),new Uint8ClampedArray(8)));});
