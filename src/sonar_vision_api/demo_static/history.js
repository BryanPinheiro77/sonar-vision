"use strict";
const $ = id => document.getElementById(id), core = globalThis.SonarPlayer;
const set = (id, value) => { $(id).textContent = value; };
const states = {recording: "Em gravação", completed: "Concluída", interrupted: "Interrompida", failed: "Falha na coleta"};
const qualities = {good: "Boa", degraded: "Degradada", invalid: "Inválida"};
const sectors = {left: "Esquerda", center: "Centro", right: "Direita", all: "Todos os setores"};
const cache = new Map();
let timeline = null, selected = null, displayed = -1, wanted = -1, generation = 0;
let playing = false, loading = false, playStarted = 0, captureStarted = 0, skipped = 0, tofPage = 0;
let selectionAbort = new AbortController(), frameAbort = new AbortController();
let pumpTimer = null, lastFetchAt = -Infinity;
function message(value) { set("player-message", value); }
function pause() { playing = false; set("play", "Reproduzir"); }
function resetRoundIdentity(title = "Selecione uma rodada", description = "Os dados reproduzidos são históricos.") {
  set("player-title", title); set("round-description", description); set("round-state", "Histórico");
  for (const id of ["history-source", "history-retention"]) set(id, "—");
  set("timecode", "00:00 / 00:00"); $("seek").value = "0";
  $("download-round").hidden = true; $("download-round").removeAttribute("href");
}
function clearCache() { for (const value of cache.values()) URL.revokeObjectURL(value.url); cache.clear(); }
function clearCanvas(value) {
  const c = $("history-frame"); c.getContext("2d").clearRect(0, 0, c.width, c.height);
  c.hidden = true; $("history-empty").hidden = false; set("history-empty-message", value);
  $("history-detections").replaceChildren(); $("history-detections").hidden = true;
  for (const id of ["history-distance", "history-quality", "history-tof-id", "history-offset", "history-id", "history-hash"]) set(id, "—");
  set("history-tof-status", "Aguardando o frame selecionado; consulte as leituras independentes abaixo.");
  set("frame-description", value);
}
async function bytes(url, maxBytes, signal) {
  const response = await fetch(url, {cache: "no-store", signal: AbortSignal.any([signal, AbortSignal.timeout(10000)])});
  if (!response.ok) throw new Error(response.status === 429 ? "Limite de consultas atingido. Aguarde e tente novamente." : response.status === 404 ? "Rodada indisponível ou expirada. Atualize a lista." : "Não foi possível consultar os dados desta rodada.");
  const declared = Number(response.headers.get("Content-Length"));
  if (declared > maxBytes) throw new Error("Resposta acima do limite de leitura.");
  const reader = response.body.getReader(), chunks = [];
  let size = 0;
  try {
    while (true) {
      const {done, value} = await reader.read(); if (done) break;
      size += value.length;
      if (size > maxBytes) { await reader.cancel(); throw new Error("Resposta acima do limite de leitura."); }
      chunks.push(value);
    }
  } finally { reader.releaseLock(); }
  const result = new Uint8Array(size); let offset = 0;
  for (const chunk of chunks) { result.set(chunk, offset); offset += chunk.length; }
  return result;
}
async function json(url, signal) { return JSON.parse(new TextDecoder().decode(await bytes(url, 16 * 1024 * 1024, signal))); }
function date(value) { return new Date(value).toLocaleString("pt-BR", {day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit"}); }
function controls() {
  const length = timeline?.frames.length ?? 0;
  $("seek").disabled = !length; $("seek").max = Math.max(0, length - 1);
  $("previous-frame").disabled = !length || displayed <= 0;
  $("next-frame").disabled = !length || displayed >= length - 1;
  const timed = length > 1 && timeline.frames[length - 1].captured_at_ms > timeline.frames[0].captured_at_ms;
  $("play").disabled = !timed; $("speed").disabled = !timed;
}
function showToF(frame) {
  const match = core.tofForFrame(timeline.tof, frame.captured_at_ms), r = match.reading;
  set("history-distance", match.state === "valid" ? r.distance_mm.toLocaleString("pt-BR") : "—");
  set("history-tof-status", {missing: "Não há leitura anterior a este frame.", valid: "Leitura anterior registrada. Não indica caminho livre.", invalid: "A leitura anterior foi informada como inválida.", stale: "Leitura anterior defasada em 5 s ou mais."}[match.state]);
  set("history-quality", r ? (qualities[r.quality] ?? r.quality) + " · " + (sectors[r.sector] ?? "setor indisponível") : "—");
  set("history-tof-id", r ? r.sequence + " / " + r.captured_at_ms + " ms" : "—");
  set("history-offset", r ? match.age_ms + " ms antes da imagem · medições distintas" : "Sem leitura anterior; não usar dados futuros.");
}
function draw(index) {
  if (!timeline || index < 0) return;
  const frame = timeline.frames[index], stored = cache.get(frame.sample_id);
  if (!stored) return;
  const c = $("history-frame"), ctx = c.getContext("2d");
  c.width = stored.image.naturalWidth; c.height = stored.image.naturalHeight;
  c.hidden = false; $("history-empty").hidden = true;
  ctx.drawImage(stored.image, 0, 0);
  const scale = 1 / Math.max(.01, Math.min(c.clientWidth / c.width, c.clientHeight / c.height));
  const detections = frame.prediction_status === "available" ? frame.predictions?.detections ?? [] : [];
  const list = $("history-detections"); list.replaceChildren();
  for (const d of detections) {
    const label = d.class_name + " · ID " + (d.track_id ?? "indisponível");
    const li = document.createElement("li"); li.textContent = label; list.append(li);
    if ($("history-boxes").checked) {
      const [x1, y1, x2, y2] = d.box, x = x1 * c.width, y = y1 * c.height;
      ctx.strokeStyle = "#00a6a6"; ctx.lineWidth = 2 * scale;
      ctx.strokeRect(x, y, (x2 - x1) * c.width, (y2 - y1) * c.height);
      ctx.font = (14 * scale) + "px system-ui";
      const top = Math.max(0, y - 24 * scale);
      ctx.fillStyle = "#123d54"; ctx.fillRect(x, top, ctx.measureText(label).width + 12 * scale, 24 * scale);
      ctx.fillStyle = "#fff"; ctx.fillText(label, x + 6 * scale, top + 18 * scale);
    }
  }
  list.hidden = !list.children.length;
  displayed = index; $("seek").value = index;
  const first = timeline.frames[0].captured_at_ms, last = timeline.frames[timeline.frames.length - 1].captured_at_ms;
  set("timecode", core.timecode(frame.captured_at_ms - first) + " / " + core.timecode(last - first));
  const interval = index > 0 ? frame.captured_at_ms - timeline.frames[index - 1].captured_at_ms : 0;
  const diagnostic = frame.prediction_status === "available" ? "Previsões originais" : "Previsões indisponíveis";
  set("frame-description", "Frame " + (index + 1) + " de " + timeline.frames.length + " · " + diagnostic + (index > 0 ? " · Intervalo entre capturas: " + interval + " ms" : ""));
  set("history-id", frame.frame_id + " / " + frame.captured_at_ms + " ms / " + (frame.predictions?.tracker_epoch ?? "epoch indisponível"));
  set("history-hash", frame.jpeg_sha256);
  showToF(frame); controls();
  if (index > 0 && timeline.frames[index - 1].predictions?.tracker_epoch && frame.predictions?.tracker_epoch !== timeline.frames[index - 1].predictions.tracker_epoch) {
    message("O tracker mudou de epoch nesta captura. IDs de epochs diferentes não formam uma trajetória contínua.");
  }
}
async function pump() {
  if (loading || !timeline || wanted < 0) return;
  const turn = generation, index = wanted, frame = timeline.frames[index];
  const delay = 100 - (performance.now() - lastFetchAt);
  if (!cache.has(frame.sample_id) && delay > 0) {
    if (pumpTimer === null) pumpTimer = setTimeout(() => { pumpTimer = null; pump(); }, delay);
    return;
  }
  loading = true;
  try {
    if (!cache.has(frame.sample_id)) {
      lastFetchAt = performance.now();
      const raw = await bytes("/v1/demo/history/" + selected + "/frames/" + frame.sample_id, 512 * 1024, frameAbort.signal);
      const digest = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", raw)), b => b.toString(16).padStart(2, "0")).join("");
      if (digest !== frame.jpeg_sha256) throw new Error("O hash da imagem não corresponde ao frame. Reprodução interrompida.");
      const url = URL.createObjectURL(new Blob([raw], {type: "image/jpeg"})), image = new Image();
      image.src = url;
      try { await image.decode(); } catch (error) { URL.revokeObjectURL(url); throw new Error("JPEG indisponível para reprodução."); }
      if (turn !== generation) { URL.revokeObjectURL(url); return; }
      cache.set(frame.sample_id, {image, url});
      while (cache.size > 2) { const key = cache.keys().next().value; URL.revokeObjectURL(cache.get(key).url); cache.delete(key); }
    }
    if (turn === generation && (playing || index === wanted)) draw(index);
  } catch (error) {
    if (turn === generation && error.name !== "AbortError") {
      pause(); wanted = -1; clearCanvas("Imagem indisponível"); message(error.message);
    }
  } finally {
    if (turn === generation) {
      loading = false;
      if (wanted >= 0 && wanted !== displayed) pump();
    }
  }
}
function seek(index) {
  pause(); wanted = Math.max(0, Math.min(index, timeline.frames.length - 1));
  clearCanvas("Carregando frame selecionado…");
  message("Capturas originais, sem interpolação. A leitura ToF mantém seu próprio tempo.");
  pump();
}
function renderTable() {
  const rows = timeline?.tof ?? [], start = tofPage * 50, table = $("tof-rows"); table.replaceChildren();
  for (const reading of rows.slice(start, start + 50)) {
    const row = document.createElement("tr");
    for (const value of [reading.sequence, reading.captured_at_ms, reading.valid ? reading.distance_mm : "Indisponível", qualities[reading.quality] ?? reading.quality]) {
      const cell = document.createElement("td"); cell.textContent = value; row.append(cell);
    }
    table.append(row);
  }
  set("tof-page", rows.length ? (start + 1) + "–" + Math.min(start + 50, rows.length) + " de " + rows.length : "Sem leituras");
  $("tof-previous").disabled = tofPage === 0; $("tof-next").disabled = start + 50 >= rows.length;
}
async function selectRound(roundId) {
  pause(); generation++; selectionAbort.abort(); frameAbort.abort();
  clearTimeout(pumpTimer); pumpTimer = null; lastFetchAt = -Infinity;
  selectionAbort = new AbortController(); frameAbort = new AbortController();
  const turn = generation;
  selected = roundId; timeline = null; displayed = -1; wanted = -1; loading = false; skipped = 0; tofPage = 0;
  resetRoundIdentity("Carregando rodada…");
  clearCache(); clearCanvas("Carregando rodada…"); controls(); renderTable();
  $("download-round").hidden = true;
  for (const button of $("round-list").querySelectorAll("button")) button.setAttribute("aria-pressed", String(button.dataset.round === roundId));
  try {
    const data = await json("/v1/demo/history/" + roundId, selectionAbort.signal);
    if (turn !== generation) return;
    if (!Array.isArray(data.frames) || !Array.isArray(data.tof) || data.frames.length > 3000 || data.tof.length > 6000) throw new Error("Rodada excede os limites do reprodutor.");
    timeline = data;
    set("player-title", "Rodada de " + date(data.round.created_at_ms));
    set("round-description", data.round.source_id + " · " + (data.round.source.kind === "simulated" ? "Fonte simulada" : "Origem ESP configurada"));
    set("round-state", states[data.round.state] ?? data.round.state);
    set("history-source", data.round.source.device_id + " / " + data.round.source.session_id + (data.round.models.backend === "simulated" ? " / inferência simulada" : ""));
    set("history-retention", "Exclusão até " + date(data.round.expires_at_ms) + " · " + (data.round.reason ?? "coleta em andamento"));
    $("download-round").href = "/v1/demo/history/" + roundId + "/download"; $("download-round").hidden = false;
    message(data.round.state === "recording" ? "Rodada ainda em gravação. Esta consulta é um recorte; atualize a lista para carregar novas capturas." : "Capturas originais, sem interpolação. A leitura ToF mantém seu próprio tempo.");
    controls(); renderTable();
    if (data.frames.length) { wanted = 0; pump(); }
    else { clearCanvas("Esta rodada não possui imagens"); set("frame-description", "As leituras ToF disponíveis podem ser consultadas abaixo ou no download."); }
    set("history-status", "Consulta concluída · dados históricos");
  } catch (error) {
    if (turn !== generation || error.name === "AbortError") return;
    resetRoundIdentity("Rodada indisponível", "Atualize a lista para consultar as rodadas disponíveis.");
    clearCanvas("Rodada indisponível"); message(error.message); set("history-status", "Falha na consulta · tente atualizar");
  }
}
async function refresh() {
  $("refresh-rounds").disabled = true;
  try {
    const data = await json("/v1/demo/history", new AbortController().signal);
    const list = $("round-list"); list.replaceChildren();
    if (!data.enabled || !data.rounds.length) {
      const p = document.createElement("p"); p.className = "empty-history";
      p.textContent = data.enabled ? "Nenhuma rodada disponível. Rodadas vencidas são excluídas." : "O histórico não foi habilitado pelo operador."; list.append(p);
      set("history-status", data.enabled ? "Sem rodadas armazenadas" : "Histórico não configurado");
      pause(); generation++; frameAbort.abort(); selectionAbort.abort(); clearCache();
      timeline = null; selected = null; displayed = -1; wanted = -1; loading = false;
      resetRoundIdentity(); clearCanvas("Sem rodada disponível"); controls(); renderTable();
      return;
    }
    for (const round of data.rounds) {
      const button = document.createElement("button"); button.className = "round-option"; button.type = "button";
      button.dataset.round = round.round_id; button.setAttribute("aria-pressed", String(round.round_id === selected));
      const title = document.createElement("strong"); title.textContent = date(round.created_at_ms);
      const source = document.createElement("span"); source.textContent = round.source_id;
      const count = document.createElement("span"); count.textContent = round.frame_count + " imagens · " + round.tof_count + " leituras · " + (states[round.state] ?? round.state);
      button.append(title, source, count); button.addEventListener("click", () => selectRound(round.round_id)); list.append(button);
    }
    await selectRound(data.rounds.some(r => r.round_id === selected) ? selected : data.rounds[0].round_id);
  } catch (error) { set("history-status", "Não foi possível atualizar as rodadas"); message(error.message); }
  finally { $("refresh-rounds").disabled = false; }
}
$("refresh-rounds").addEventListener("click", refresh);
$("seek").addEventListener("input", () => seek(Number($("seek").value)));
$("previous-frame").addEventListener("click", () => seek(displayed - 1));
$("next-frame").addEventListener("click", () => seek(displayed + 1));
$("history-boxes").addEventListener("change", () => { if (!$("history-frame").hidden) draw(displayed); });
$("play").addEventListener("click", () => {
  if (playing) { pause(); return; }
  if (!timeline?.frames.length) return;
  if (displayed >= timeline.frames.length - 1) wanted = 0;
  else wanted = Math.max(0, displayed);
  captureStarted = timeline.frames[wanted].captured_at_ms; playStarted = performance.now();
  playing = true; set("play", "Pausar"); message("Reproduzindo capturas originais. Limite de 10 imagens/s; em velocidades altas, alguns frames podem não ser exibidos."); pump();
});
$("speed").addEventListener("change", () => { if (playing && displayed >= 0) { captureStarted = timeline.frames[displayed].captured_at_ms; playStarted = performance.now(); } });
$("tof-previous").addEventListener("click", () => { tofPage--; renderTable(); });
$("tof-next").addEventListener("click", () => { tofPage++; renderTable(); });
window.addEventListener("resize", () => { if (!$("history-frame").hidden) draw(displayed); });
document.addEventListener("visibilitychange", () => { if (document.hidden) pause(); });
window.addEventListener("pagehide", () => { pause(); generation++; frameAbort.abort(); selectionAbort.abort(); clearCache(); clearCanvas("Página fechada"); timeline = null; });
setInterval(() => {
  if (!playing || !timeline) return;
  const position = core.positionAfter(timeline.frames, captureStarted, performance.now() - playStarted, Number($("speed").value));
  if (position.index > wanted + 1) skipped += position.index - wanted - 1;
  wanted = position.index;
  if (wanted !== displayed) pump();
  if (position.ended) { pause(); message("Fim da rodada. " + (skipped ? skipped + " frames não exibidos pela velocidade/limite de reprodução. Use o avanço por frame para revisar todos." : "Use o avanço por frame para revisar cada captura.")); }
}, 100);
refresh();
