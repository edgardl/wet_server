// No npm dependencies. Runs only owned localhost Flask and headless Edge children.
import {spawn} from 'node:child_process';
import {mkdtemp, readFile, writeFile, mkdir, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const python=process.env.LONK_PYTHON||path.join(root,'.venv','Scripts','python.exe');
const edge=process.env.LONK_EDGE||'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const profile=await mkdtemp(path.join(tmpdir(),'lonkworld-browser-smoke-'));
const artifacts=path.join(root,'tests','artifacts');
let server,browser,control,page;
const sockets=[];
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const deadline=Date.now()+50000;
async function until(fn,label){while(Date.now()<deadline){try{const value=await fn();if(value)return value;}catch{}await delay(100);}throw Error('Timed out: '+label);}
async function connect(url){
 const ws=new WebSocket(url);sockets.push(ws);await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject;});
 let seq=0;const pending=new Map();
 ws.onmessage=e=>{const message=JSON.parse(e.data);if(message.id&&pending.has(message.id)){const {resolve,reject,timer}=pending.get(message.id);clearTimeout(timer);pending.delete(message.id);message.error?reject(Error(JSON.stringify(message.error))):resolve(message.result);}};
 return {send(method,params={}){return new Promise((resolve,reject)=>{const id=++seq,timer=setTimeout(()=>{pending.delete(id);reject(Error('CDP timeout '+method));},8000);pending.set(id,{resolve,reject,timer});ws.send(JSON.stringify({id,method,params}));});}};
}
async function evaluate(expression){const result=await page.send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(result.exceptionDetails)throw Error(JSON.stringify(result.exceptionDetails));return result.result.value;}
try{
 let output='';
 server=spawn(python,['-u','-B','-c',"from werkzeug.serving import make_server; from app import app; s=make_server('127.0.0.1',0,app); print(s.server_port,flush=True); s.serve_forever()"],{cwd:path.join(root,'docker'),windowsHide:true,stdio:['ignore','pipe','pipe']});
 server.stdout.on('data',d=>output+=d);server.stderr.on('data',()=>{});
 const port=await until(()=>/^\d+/.exec(output)?.[0],'local Flask startup');
 browser=spawn(edge,['--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--remote-debugging-port=0',`--user-data-dir=${profile}`,'about:blank'],{windowsHide:true,stdio:'ignore'});
 const devtools=await until(async()=>{const text=await readFile(path.join(profile,'DevToolsActivePort'),'utf8');const [port,endpoint]=text.trim().split(/\r?\n/);return {port,endpoint};},'headless Edge startup');
 control=await connect(`ws://127.0.0.1:${devtools.port}${devtools.endpoint}`);
 const target=await control.send('Target.createTarget',{url:'about:blank'});
 const targets=await (await fetch(`http://127.0.0.1:${devtools.port}/json/list`)).json();
 page=await connect(targets.find(t=>t.id===target.targetId).webSocketDebuggerUrl);
 await page.send('Page.enable');await page.send('Runtime.enable');
 await page.send('Emulation.setDeviceMetricsOverride',{width:1280,height:1000,deviceScaleFactor:1,mobile:false});
 await page.send('Page.navigate',{url:`http://127.0.0.1:${port}/lonkworld`});
 await until(()=>evaluate("document.querySelector('#day')?.textContent==='Day 0 · 5 Lonks' && !document.querySelector('#step').disabled"),'fresh five Lonks');
 await evaluate("document.querySelector('#message').value='starlingsong 123'; document.querySelector('#talk').requestSubmit();");
 await until(()=>evaluate("document.querySelector('#message').value==='' && document.querySelector('#details').textContent.includes('starlingsong') && !document.querySelector('#step').disabled"),'talk teaches distinctive word');
 const taught=await evaluate("JSON.parse(localStorage.getItem('lonkworld-xc-world-v2')).lonks[0].linguistics.tokens");
 assert.ok(taught.starlingsong);assert.ok(taught['123']);
 await evaluate("document.querySelector('#step').click()");
 await until(()=>evaluate("document.querySelector('#day').textContent.startsWith('Day 1 ·') && !document.querySelector('#step').disabled"),'step advances one day');
 const before=await evaluate("localStorage.getItem('lonkworld-xc-world-v2')");
 await page.send('Page.reload',{ignoreCache:true});
 await until(()=>evaluate("document.querySelector('#day')?.textContent.startsWith('Day 1 ·') && !document.querySelector('#step').disabled"),'reload restores day');
 assert.equal(await evaluate("localStorage.getItem('lonkworld-xc-world-v2')"),before);
 assert.equal(await evaluate("document.querySelector('#export').disabled"),false);
 assert.ok(await evaluate("document.querySelector('#details').textContent.includes('starlingsong')"));
 await mkdir(artifacts,{recursive:true});
 const shot=await page.send('Page.captureScreenshot',{format:'png',captureBeyondViewport:true});
 await writeFile(path.join(artifacts,'lonkworld-browser.png'),Buffer.from(shot.data,'base64'));
 const report={ok:true,browser:'headless Microsoft Edge',checks:['fresh five Lonks','talk learns starlingsong and numeric 123','Step advances to day 1','reload preserves exact opaque world state','learned language remains visible','export enabled'],screenshot:'tests/artifacts/lonkworld-browser.png'};
 await writeFile(path.join(artifacts,'browser-smoke.json'),JSON.stringify(report,null,2));
 console.log(JSON.stringify(report,null,2));
}finally{
 if(control){try{await control.send('Browser.close');}catch{}}
 for(const ws of sockets)ws.close();
 if(browser&&!browser.killed)browser.kill();
 if(server&&!server.killed)server.kill();
 await delay(500);
 // This is exclusively the unique temporary profile created by this script.
 if(path.dirname(profile)===path.resolve(tmpdir())&&path.basename(profile).startsWith('lonkworld-browser-smoke-'))await rm(profile,{recursive:true,force:true,maxRetries:3}).catch(()=>{});
}
