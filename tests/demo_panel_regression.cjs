// Runs the shipped JS with controlled network/clock and minimal DOM, no package install.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const elements = new Map();
function element(id) {
  if (!elements.has(id)) elements.set(id, {
    textContent: '', hidden: true, checked: true, dataset: {}, children: [], clientWidth: 320,
    getContext: () => ({clearRect(){}}),
    replaceChildren(...rows){ this.children=rows; },
    append(row){ this.children.push(row); },
    addEventListener(name, handler){ this[name]=handler; },
    attributes: {},
    setAttribute(name, value){ this.attributes[name] = value; },
    getAttribute(name){ return this.attributes[name] ?? null; },
    animate(){ this.animations = (this.animations ?? 0) + 1; },
  });
  return elements.get(id);
}
let now = 0, networkMode = 'image-failure', scheduled = 0;
const payload = () => ({source:{device_id:'test',session_id:'boot',kind:'simulated'},
  backend:'simulated', stale_ms:5000, retention_ms:30000, rejected_tof:0,
  image:{state:'receiving',age_ms:0,data:{frame_id:'1',captured_at_ms:1000,
    jpeg_sha256:'a'.repeat(64),received_at_ms:0,inference:'available',predictions:{tracker_epoch:'e',detections:[]}}},
  tof:{state:'receiving',age_ms:0,data:{valid:true,distance_mm:1250,quality:'good',sector:'all',
    aggregation:'min_valid_8x8',sequence:'1',captured_at_ms:1100,received_at_ms:0}}});
const sandbox = {
  document:{hidden:true,getElementById:element,createElement:()=>element('item')},
  window:{addEventListener(){},matchMedia:()=>({matches:false})},performance:{now:()=>now},
  setTimeout:()=>{scheduled++;},setInterval(){},
  URL:{revokeObjectURL(){}},AbortSignal:{timeout(){}},
  console,
  fetch: async url => {
    if(networkMode==='snapshot-failure') throw Error('disconnected');
    if(networkMode==='pause-in-flight') element('pause').click();
    if(url.includes('snapshot')) return {ok:true,json:async()=>payload()};
    return {ok:false,status:409}; // JPEG replaced while valid ToF snapshot arrived
  },
};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync('src/sonar_vision_api/demo_static/panel.js','utf8') +
  '\nglobalThis.api={update,render,readings:()=>recentReadings,accept(value){last=value;fetchedAt=performance.now();online=true;observeTelemetry(value);render();}};',sandbox);
(async()=>{
  sandbox.document.hidden=false;
  await sandbox.api.update();
  assert.equal(element('tof-state').textContent,'Recebendo');
  assert.equal(element('distance').textContent,(1250).toLocaleString('pt-BR'));
  assert.equal(element('image-state').textContent,'Servidor indisponível');
  sandbox.api.render(); // subsequent age ticks must not overwrite the image failure
  assert.equal(element('tof-state').textContent,'Recebendo');
  assert.equal(element('distance').animations,1,'age ticks must not restart number feedback');
  assert.equal(element('camera-panel').dataset.preview,'true','scripted source opens the clearly labeled presentation');
  element('preview-toggle').click();
  assert.equal(element('illustration').hidden,true);
  element('preview-toggle').click();
  assert.equal(element('illustration').hidden,false);
  assert.equal(element('camera-panel').dataset.preview,'true');
  assert.equal(element('distance').textContent,(1250).toLocaleString('pt-BR'),'illustration must not replace live ToF');
  assert.equal(element('image-state').textContent,'Servidor indisponível','illustration must not fake an image reception');
  element('preview-toggle').click();
  assert.equal(element('illustration').hidden,true);
  assert.equal(element('preview-toggle').getAttribute('aria-pressed'),'false');
  now=5001;sandbox.api.render();
  assert.equal(element('tof-state').textContent,'Dados atrasados');
  assert.equal(element('distance').textContent,'—');
  networkMode='snapshot-failure';await sandbox.api.update();
  assert.equal(element('tof-state').textContent,'Servidor indisponível');
  assert.equal(element('image-state').textContent,'Servidor indisponível');
  networkMode='pause-in-flight';const before=scheduled;await sandbox.api.update();
  assert.equal(scheduled,before+1,'pause during fetch must still schedule resume polling');
  sandbox.window.matchMedia=()=>({matches:true});
  const animations=element('distance').animations;
  element('pause').click();networkMode='image-failure';now=0;
  await sandbox.api.update();
  assert.equal(element('distance').animations,animations,'reduced motion must suppress numeric animation');
  element('preview-toggle').click();
  assert.equal(element('camera-panel').dataset.preview,'true');
  element('pause').click();
  assert.equal(element('distance').textContent,'—','pause must clear distance even in illustration mode');
  assert.equal(element('distance-marker').getAttribute('visibility'),'hidden');
  assert.equal(element('trend-line').getAttribute('d'),'');
  element('pause').click();
  element('boxes').checked=false;element('boxes').change();
  assert.equal(element('illustration-box').hidden,true,'checkbox controls illustration marker too');
  const ingest=(sequence,value,valid=true,session='boot')=>{
    const p=payload();p.source.session_id=session;p.tof.data.sequence=String(sequence);
    p.tof.data.distance_mm=value;p.tof.data.valid=valid;
    sandbox.api.accept(p);
  };
  ingest(2,0);
  assert.equal(element('distance').textContent,'0','valid zero is a measurement');
  assert.equal(element('distance-marker').getAttribute('visibility'),'visible');
  const count=sandbox.api.readings().length;ingest(2,0);
  assert.equal(sandbox.api.readings().length,count,'duplicate sequence must not grow trend');
  now+=2000;ingest(3,null,false);
  assert.equal(element('distance').textContent,'—');
  assert.equal(element('trend-line').getAttribute('d'),'','invalid measurement must not look current');
  now+=2000;ingest(4,4500);
  assert.equal(element('distance-fill').getAttribute('width'),'296');
  assert.match(element('distance-scale').getAttribute('aria-label'),/acima da escala/);
  assert.equal((element('trend-line').getAttribute('d').match(/M/g)||[]).length,2,'invalid reading breaks the line');
  now+=6000;ingest(5,2200);
  assert.equal((element('trend-line').getAttribute('d').match(/M/g)||[]).length,3,'stale gap must not be connected');
  for(let i=6;i<45;i++){now+=500;ingest(i,2000+i);}
  assert.ok(sandbox.api.readings().length<=24,'trend memory is bounded');
  now+=30001;sandbox.api.render();
  assert.equal(sandbox.api.readings().length,0,'all samples expire within 30 seconds');
  ingest(1,1400,true,'new-boot');
  assert.equal(sandbox.api.readings().length,1,'new session clears old readings');
  const ended=payload();ended.ended=true;sandbox.api.accept(ended);
  assert.equal(sandbox.api.readings().length,0,'ending session clears trend immediately');
  const live=payload();live.source.kind='esp32';live.backend='ultralytics';sandbox.api.accept(live);
  assert.equal(element('illustration').hidden,true,'real backend must default to verified JPEG');
  console.log('demo JS: independent channels, pause, illustration, reduced motion, gauge, bounded trend, gaps and session isolation passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
