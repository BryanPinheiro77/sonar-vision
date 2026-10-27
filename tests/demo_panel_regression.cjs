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
    setAttribute(){},
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
  window:{addEventListener(){}},performance:{now:()=>now},
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
  '\nglobalThis.api={update,render};',sandbox);
(async()=>{
  sandbox.document.hidden=false;
  await sandbox.api.update();
  assert.equal(element('tof-state').textContent,'Recebendo');
  assert.equal(element('distance').textContent,(1250).toLocaleString('pt-BR'));
  assert.equal(element('image-state').textContent,'Servidor indisponível');
  sandbox.api.render(); // subsequent age ticks must not overwrite the image failure
  assert.equal(element('tof-state').textContent,'Recebendo');
  now=5001;sandbox.api.render();
  assert.equal(element('tof-state').textContent,'Dados atrasados');
  assert.equal(element('distance').textContent,'—');
  networkMode='snapshot-failure';await sandbox.api.update();
  assert.equal(element('tof-state').textContent,'Servidor indisponível');
  assert.equal(element('image-state').textContent,'Servidor indisponível');
  networkMode='pause-in-flight';const before=scheduled;await sandbox.api.update();
  assert.equal(scheduled,before+1,'pause during fetch must still schedule resume polling');
  console.log('demo JS: independent JPEG/ToF failures, ageing, disconnect and pause race passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
