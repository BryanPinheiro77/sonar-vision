const assert = require('node:assert/strict');
const p = require('../src/sonar_vision_api/demo_static/player-core.js');
const frames = [{captured_at_ms:1000},{captured_at_ms:2000},{captured_at_ms:9000}];
const readings = [
  {captured_at_ms:500,valid:true,distance_mm:1500},
  {captured_at_ms:1500,valid:false,distance_mm:null},
  {captured_at_ms:10000,valid:true,distance_mm:20},
];
assert.equal(p.tofForFrame(readings,400).state,'missing');
assert.equal(p.tofForFrame(readings,1000).reading.distance_mm,1500);
assert.equal(p.tofForFrame(readings,2000).state,'invalid');
assert.equal(p.tofForFrame(readings,6500).state,'stale');
assert.equal(p.tofForFrame(readings,9000).reading.distance_mm,null,'must not use future 20mm reading');
assert.equal(p.frameAt(frames,5000),1,'a capture gap must not create an interpolated frame');
assert.deepEqual(p.positionAfter(frames,1000,1000,8),{index:2,ended:true});
assert.deepEqual(p.positionAfter(frames,1000,1000,.5),{index:0,ended:false});
assert.equal(p.timecode(125000),'02:05');
assert.equal(p.frameAt([],1000),0);
console.log('player core: independent ToF, invalid/stale/future readings, gaps, speed and end passed');
