/* Stored policy decisions only. No playback, policy execution or device control. */
(function (root) {
  "use strict";
  function describe(prediction, historical = false) {
    const missing = {status: "Áudio não registrado", text: "—",
      note: "Esta captura não tem registro da sugestão de áudio."};
    if (!prediction || !Object.hasOwn(prediction, "audio")) return missing;
    if (prediction.audio === null) return {status: "Sem sugestão", text: "—",
      note: "A API não retornou uma sugestão de fala para esta imagem."};
    const audio = prediction.audio;
    if (typeof audio !== "object" || typeof audio.text !== "string" ||
        !audio.text.trim() || [...audio.text].length > 120 ||
        typeof prediction.message_id !== "string" || typeof prediction.frame_id !== "string" ||
        !Number.isSafeInteger(prediction.captured_at_ms) ||
        audio.observation_id !== prediction.message_id ||
        audio.frame_id !== prediction.frame_id ||
        audio.captured_at_ms !== prediction.captured_at_ms) return missing;
    return {status: historical ? "Registro histórico" : "Frase registrada", text: audio.text,
      note: "Decisão registrada para esta imagem. Não confirma reprodução no ESP."};
  }
  root.SonarAudioView = {describe};
  if (typeof module !== "undefined" && module.exports) module.exports = {describe};
})(globalThis);
