// Exercise the shipped history state transitions with controlled HTTP/DOM.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const elements=new Map();
function el(id){
 if(!elements.has(id)) elements.set(id,{textContent:'',hidden:false,value:'0',dataset:{},children:[],attrs:{},
  replaceChildren(...rows){this.children=rows;},append(...rows){this.children.push(...rows);},
  setAttribute(name,value){this.attrs[name]=value;},removeAttribute(name){delete this.attrs[name];},
  getAttribute(name){return this.attrs[name]??null;},querySelectorAll(){return[];},addEventListener(){},
  getContext(){return{clearRect(){}};}});
 return elements.get(id);
}
let mode='empty';
const context={document:{getElementById:el,createElement:()=>({textContent:'',append(){}}),addEventListener(){}},
 window:{addEventListener(){}},SonarPlayer:require('../src/sonar_vision_api/demo_static/player-core.js'),
 AbortController,AbortSignal,TextDecoder,Uint8Array,Map,performance,URL:{revokeObjectURL(){}},
 setInterval(){},setTimeout(){},clearTimeout(){},console,
 fetch:async()=> mode==='error'?new Response('{}',{status:404}):new Response(JSON.stringify({enabled:true,rounds:[]}),{status:200}),
};
vm.createContext(context);
vm.runInContext(fs.readFileSync('src/sonar_vision_api/demo_static/history.js','utf8')+'\nglobalThis.api={refresh,selectRound};',context);
function staleIdentity(){
 el('download-round').hidden=false;el('download-round').setAttribute('href','/old-round/download');
 for(const id of ['player-title','round-description','history-source','history-retention','timecode'])el(id).textContent='old-round';
 el('seek').value='19';
}
(async()=>{
 await new Promise(resolve=>setImmediate(resolve));
 staleIdentity();await context.api.refresh();
 assert.equal(el('download-round').hidden,true);
 assert.equal(el('download-round').getAttribute('href'),null);
 assert.equal(el('player-title').textContent,'Selecione uma rodada');
 assert.equal(el('timecode').textContent,'00:00 / 00:00');assert.equal(el('seek').value,'0');
 assert.equal(el('history-source').textContent,'—');assert.equal(el('history-retention').textContent,'—');
 staleIdentity();mode='error';await context.api.selectRound('a'.repeat(32));
 assert.equal(el('download-round').hidden,true);assert.equal(el('download-round').getAttribute('href'),null);
 assert.equal(el('player-title').textContent,'Rodada indisponível');assert.equal(el('history-source').textContent,'—');
 console.log('history JS: expired/empty rounds and failed selection clear identity, timecode and download');
})().catch(error=>{console.error(error);process.exitCode=1;});
