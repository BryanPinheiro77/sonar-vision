const assert = require('node:assert/strict');
const {describe} = require('../src/sonar_vision_api/demo_static/audio-view.js');
const prediction = {message_id:'obs',frame_id:'1',captured_at_ms:1000,
  audio:{observation_id:'obs',frame_id:'1',captured_at_ms:1000,text:'Escada de subida'}};
assert.equal(describe(prediction).text,'Escada de subida');
assert.equal(describe(prediction).status,'Frase registrada');
assert.equal(describe(prediction,true).status,'Registro histórico');
assert.match(describe(prediction).note,/Não confirma reprodução/);
assert.equal(describe({...prediction,audio:null}).status,'Sem sugestão');
assert.equal(describe({message_id:'old'}).status,'Áudio não registrado');
assert.equal(describe({audio:{text:'Outra captura'}}).text,'—');
for(const audio of [false,'fala',{...prediction.audio,frame_id:'2'},
  {...prediction.audio,observation_id:'other'},{...prediction.audio,captured_at_ms:999},
  {...prediction.audio,text:'x'.repeat(121)}]) {
  assert.equal(describe({...prediction,audio}).text,'—');
}
console.log('audio JS: exact-frame text, null, legacy, history and bad-reference rejection');
