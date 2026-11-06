const fs=require('fs'),{spawn}=require('child_process');
const {chromium}=require('C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1103-91-0_26.1103.91.0_x64__3k8sg7r9htsxt/dependencies/node/node_modules/playwright');
(async()=>{const server=spawn('python',['-m','http.server','18772','--bind','127.0.0.1'],{windowsHide:true});await new Promise(r=>setTimeout(r,1000));let browser;try{
 browser=await chromium.launch({channel:'msedge',headless:true});const page=await browser.newPage(),bad=[];
 page.on('request',r=>{if(!r.url().startsWith('http://127.0.0.1:18772')&&!r.url().startsWith('data:'))bad.push(r.url());});
 await page.goto('http://127.0.0.1:18772/tests/rich-browser.html');await page.waitForFunction(()=>document.querySelector('#result').textContent!=='running');
 const result=await page.locator('#result').innerText();console.log(result);if(result.startsWith('FAIL')||bad.length)throw Error('rich HTML QA failed');
 const data=fs.readFileSync('C:/Windows/Fonts/arial.ttf').toString('base64');
 const ok=await page.evaluate(async data=>{const m=await import('../fonts.js');const f=await m.readFont(new File([Uint8Array.from(atob(data),c=>c.charCodeAt(0))],'Local Arial.ttf'));await m.loadFonts([f]);return document.fonts.check('20px "Local Arial"');},data);
 if(!ok)throw Error('FontFace registration failed');
 const aliases=await page.evaluate(async data=>{
  const {importPackage}=await import('../packages.js'),bytes=Uint8Array.from(atob(data),c=>c.charCodeAt(0));
  const html='<style>@font-face{font-family:ARIAL;src:url("Case Demo.ttf")}@font-face{font-family:CASE DEMO;src:url("Case Demo.ttf")}</style><section data-export-frame style="width:600px;height:400px">Text</section>';
  const files=new Map([['index.html',new File([html],'index.html')],['Case Demo.ttf',new File([bytes],'Case Demo.ttf')],['case demo.ttf',new File([bytes],'case demo.ttf')],['ARIAL.ttf',new File([bytes],'ARIAL.ttf')]]);
  const {piece}=await importPackage(files,'test');return piece.fonts?.map(f=>f.name);
 },data);if(aliases.length!==1||aliases[0]!=='Case Demo')throw Error('font aliases collided: '+aliases);console.log('Font Unicode/case import aliases: PASS');
await page.goto('http://127.0.0.1:18772/tests/fonts-browser.html');await page.waitForFunction(()=>document.querySelector('#result').textContent!=='running');if(await page.locator('#result').innerText()!=='PASS')throw Error('Font gallery failed');console.log('Font gallery: PASS');console.log('FontFace local real: PASS; external network: 0');
 }finally{if(browser)await browser.close();server.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
