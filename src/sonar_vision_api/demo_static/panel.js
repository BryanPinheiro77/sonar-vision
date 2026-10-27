"use strict";
const el = (id) => document.getElementById(id);
const labels = {waiting: "Aguardando dados", receiving: "Recebendo", stale: "Dados atrasados", expired: "Dados expirados", invalid: "Leitura inválida", offline: "Servidor indisponível", paused: "Atualização pausada"};
const quality = {good: "Boa", degraded: "Degradada", invalid: "Inválida"};
const sector = {left: "Esquerda", center: "Centro", right: "Direita", all: "Todos"};
let paused = false, online = false, last = null, fetchedAt = 0, pixels = null, pixelKey = null, objectUrl = null;
let generation = 0, imageFailed = false;
let presentationSession = null, readingSequence = null;
let recentReadings = [];
function text(id, value) {
  const target = el(id), next = String(value);
  if (target.textContent === next) return;
  target.textContent = next;
  if (id === "distance" && next !== "—" && target.animate && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    target.animate([{opacity: .45}, {opacity: 1}], {duration: 200, easing: "ease-out"});
  }
}
function badge(id, state) { text(id, labels[state]); el(id).dataset.state = state; }
function connection(message, status) {
  text("connection", status === "receiving" ? "Conectado" : status === "paused" ? "Pausado" : "Desconectado");
  el("connection").setAttribute("title", message);
  el("connection").dataset.state = status;
}
function localAge(channel) { return channel.age_ms + performance.now() - fetchedAt; }
function state(channel) {
  if (paused) return "paused";
  if (!online) return "offline";
  if (channel === last.image && imageFailed) return "offline";
  return channel.data && localAge(channel) >= last.stale_ms ? "stale" : channel.state;
}
function stamp(channel) { return new Date(channel.data.received_at_ms).toLocaleTimeString("pt-BR") + " / há " + (localAge(channel) / 1000).toFixed(1) + " s"; }
function clearImage(message) {
  pixels = null; pixelKey = null;
  if (objectUrl) URL.revokeObjectURL(objectUrl);
  objectUrl = null;
  const canvas = el("frame");
  canvas.getContext("2d").clearRect(0, 0, canvas.width, canvas.height);
  canvas.hidden = true; el("image-empty").hidden = false;
  el("detections").replaceChildren(); el("detections").hidden = true;
  text("image-empty-message", message);
}
function draw() {
  if (!pixels || !last?.image.data) return;
  const frame = last.image.data;
  if (pixelKey !== frame.frame_id + ":" + frame.jpeg_sha256) return;
  const canvas = el("frame"), ctx = canvas.getContext("2d");
  canvas.width = pixels.naturalWidth; canvas.height = pixels.naturalHeight;
  canvas.hidden = false;
  const displayScale = Math.min(canvas.clientWidth / canvas.width, canvas.clientHeight / canvas.height);
  const scale = 1 / Math.max(.01, displayScale);
  ctx.drawImage(pixels, 0, 0);
  if (el("boxes").checked && frame.inference === "available") {
    for (const box of frame.predictions.detections) {
      const [x1, y1, x2, y2] = box.box;
      const x = x1 * canvas.width, y = y1 * canvas.height;
      ctx.strokeStyle = "#00a6a6"; ctx.lineWidth = 2 * scale;
      ctx.strokeRect(x, y, (x2 - x1) * canvas.width, (y2 - y1) * canvas.height);
      ctx.font = (14 * scale) + "px system-ui";
      const label = box.class_name + " · ID " + (box.track_id ?? "indisponível");
      const top = Math.max(0, y - 24 * scale);
      ctx.fillStyle = "#c8f4f5"; ctx.fillRect(x, top, ctx.measureText(label).width + 12 * scale, 24 * scale);
      ctx.fillStyle = "#123d54"; ctx.fillText(label, x + 6 * scale, top + 18 * scale);
    }
  }
  canvas.hidden = false; el("image-empty").hidden = true;
  const list = el("detections"); list.replaceChildren();
  if (frame.inference === "available") {
    const rows = frame.predictions.detections;
    for (const d of rows) {
      const item = document.createElement("li");
      item.textContent = d.class_name + " · ID " + (d.track_id ?? "indisponível"); list.append(item);
    }
    if (!rows.length) { const item = document.createElement("li"); item.textContent = "Nenhuma detecção neste frame; não confirma caminho livre."; list.append(item); }
  }
  list.hidden = !list.children.length;
}
function render() {
  if (!last) return;
  for (const channel of [last.image, last.tof]) {
    if (channel.data && localAge(channel) >= last.retention_ms) { channel.data = null; channel.state = "expired"; }
  }
  const image = last.image, tof = last.tof;
  badge("image-state", state(image)); badge("tof-state", state(tof));
  if (image.data) {
    text("image-time", stamp(image));
    text("image-id", image.data.frame_id + " / " + image.data.captured_at_ms + " ms");
    text("image-hash", image.data.jpeg_sha256);
    text("epoch", image.data.predictions?.tracker_epoch ?? "—");
    text("inference", imageFailed ? "JPEG indisponível · nova tentativa automática" : {pending: "Imagem recebida · inferência pendente", available: "Previsões deste frame", unavailable: "Inferência indisponível"}[image.data.inference]);
  } else {
    clearImage(last.ended ? "Sessão encerrada. O operador deve selecionar uma nova sessão." : "Sem JPEG disponível. Aguardando envio da origem.");
    for (const id of ["image-time", "image-id", "image-hash", "epoch"]) text(id, "—");
    text("inference", "Inferência indisponível");
  }
  const t = tof.data;
  text("distance", t && t.valid && state(tof) === "receiving" ? t.distance_mm.toLocaleString("pt-BR") : "—");
  text("tof-explanation", t ? (state(tof) === "stale" ? "Leitura atrasada. Aguarde uma medição nova." : t.valid ? "Distância medida pelo sensor; não indica caminho livre." : "O sensor informou leitura inválida. Nenhuma distância disponível.") : "Nenhuma leitura disponível. Ausência não indica caminho livre.");
  text("quality", t ? quality[t.quality] : "—");
  text("aggregation", t ? sector[t.sector] + " / " + (t.aggregation === "zone" ? "zona " + t.zone : "mínimo das zonas válidas 8×8") : "—");
  text("tof-id", t ? t.sequence + " / " + t.captured_at_ms + " ms" : "—");
  text("tof-time", t ? stamp(tof) : "—");
  text("rejected", last.rejected_tof);
  text("tof-age", t ? "há " + Math.max(0, Math.floor(localAge(tof) / 1000)) + " s" : "—");
  text("zone", t ? t.aggregation === "zone" ? String(t.zone) : "8 × 8" : "—");
  const preview = el("camera-panel").dataset.preview === "true";
  const rows = image.data?.inference === "available" && !imageFailed ? image.data.predictions.detections : null;
  text("detection-count", preview ? "1 objeto ilustrativo" : rows ? rows.length + (rows.length === 1 ? " objeto detectado" : " objetos detectados") : "Sem previsões");
  renderTelemetry();
  text("offset", image.data && t ? "ToF − imagem: " + (t.captured_at_ms - image.data.captured_at_ms) + " ms no relógio da sessão. Capturas distintas; não implica sincronismo ou associação espacial." : "Sem dados suficientes para comparar as capturas.");
}
async function fetchBounded(url, type) {
  const response = await fetch(url, {cache: "no-store", signal: AbortSignal.timeout(4000)});
  if (!response.ok) throw new Error("HTTP " + response.status);
  return type === "json" ? response.json() : response.blob();
}
async function update() {
  const attempt = generation;
  let snapshotSucceeded = false;
  try {
  if (!paused && !document.hidden) {
    try {
      const next = await fetchBounded("/v1/demo/snapshot", "json");
      if (attempt !== generation || paused) return;
      last = next; fetchedAt = performance.now(); online = true; imageFailed = false;
      snapshotSucceeded = true;
      connection("Servidor conectado · atualização a cada 2 s", "receiving");
      text("source-kind", next.source.kind === "simulated" ? "DADOS SIMULADOS" : "ORIGEM ESP32");
      el("source-kind").dataset.kind = next.source.kind;
      text("source", "Sessão " + next.source.session_id + " · Atualização a cada 2 s" + (next.backend === "simulated" ? " · Inferência simulada" : ""));
      text("source-details", next.source.device_id + " / " + next.source.session_id + " / " + next.backend);
      observeTelemetry(next);
      const f = next.image.data, key = f ? f.frame_id + ":" + f.jpeg_sha256 : null;
      if (key !== pixelKey) {
        clearImage("Carregando JPEG correspondente do servidor…");
        render();
        if (f) {
          const blob = await fetchBounded("/v1/demo/image?frame_id=" + encodeURIComponent(f.frame_id) + "&sha256=" + f.jpeg_sha256, "blob");
          const bytes = await blob.arrayBuffer();
          const digest = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)), b => b.toString(16).padStart(2, "0")).join("");
          if (digest !== f.jpeg_sha256) throw new Error("Hash divergente");
          if (attempt !== generation || paused) return;
          const url = URL.createObjectURL(blob), img = new Image();
          img.src = url;
          try { await img.decode(); } catch (error) { URL.revokeObjectURL(url); throw error; }
          if (attempt !== generation || paused) { URL.revokeObjectURL(url); return; }
          objectUrl = url; pixels = img; pixelKey = key;
        }
      }
      render(); draw();
    } catch (error) {
      if (attempt === generation) {
        online = snapshotSucceeded; imageFailed = true;
        connection(snapshotSucceeded ? "Servidor conectado · JPEG indisponível; nova tentativa em 2 s." : "Falha de atualização. Nova tentativa automática em 2 s.", snapshotSucceeded ? "receiving" : "offline");
        render();
        clearImage("Imagem indisponível nesta atualização. Aguardando o servidor.");
      }
    }
  }
  } finally { setTimeout(update, 2000); }
}
el("boxes").addEventListener("change", () => {
  el("illustration-box").hidden = !el("boxes").checked;
  draw();
});
window.addEventListener("resize", draw);
el("pause").addEventListener("click", () => {
  paused = !paused; generation++;
  el("pause").setAttribute("aria-pressed", String(paused));
  text("pause", paused ? "Retomar" : "Pausar");
  el("pause").setAttribute("aria-label", paused ? "Retomar atualização" : "Pausar atualização");
  if (paused) { connection("Atualização pausada · dados continuam envelhecendo", "paused"); clearImage("Atualização pausada. Retome para consultar o servidor."); text("distance", "—"); renderTelemetry(); }
});
setInterval(() => { if (last) { render(); if (paused) text("distance", "—"); } }, 250);
window.addEventListener("pagehide", () => { generation++; clearImage("Página fechada."); last = null; recentReadings = []; readingSequence = null; });
update();
const previewToggle = el("preview-toggle");
if (previewToggle) previewToggle.addEventListener("click", () => {
  setPreview(previewToggle.getAttribute("aria-pressed") !== "true");
});

function setPreview(open) {
  el("preview-toggle").setAttribute("aria-pressed", String(open));
  text("preview-toggle", open ? "Ver JPEG recebido" : "Ver cena ilustrativa");
  el("illustration").hidden = !open;
  el("illustration-note").hidden = !open;
  el("illustration-box").hidden = !el("boxes").checked;
  el("camera-panel").dataset.preview = String(open);
  if (last) render();
  if (!open) draw();
}

function observeTelemetry(snapshot) {
  const session = JSON.stringify([snapshot.source.device_id, snapshot.source.session_id, snapshot.source.kind, snapshot.backend]);
  if (presentationSession !== session) {
    presentationSession = session;
    recentReadings = []; readingSequence = null;
    // A cena é uma apresentação optativa da fonte roteirizada, nunca fallback de JPEG.
    setPreview(snapshot.source.kind === "simulated" && snapshot.backend === "simulated");
  }
  if (snapshot.ended) { recentReadings = []; readingSequence = null; return; }
  const reading = snapshot.tof.data;
  if (!reading || readingSequence === reading.sequence || snapshot.tof.age_ms >= snapshot.stale_ms) return;
  readingSequence = reading.sequence;
  recentReadings.push({at: performance.now() - snapshot.tof.age_ms,
    value: reading.valid ? reading.distance_mm : null});
  recentReadings = recentReadings.slice(-24);
}

function renderTelemetry() {
  if (!last) return;
  const t = last.tof.data, available = t?.valid && state(last.tof) === "receiving";
  el("tof-explanation").hidden = Boolean(available && t.distance_mm <= 4000);
  if (available && t.distance_mm > 4000) text("tof-explanation", "Acima da escala de 4.000 mm; a leitura permanece indicada acima.");
  const ratio = available ? Math.min(1, Math.max(0, t.distance_mm / 4000)) : 0;
  const x = 2 + ratio * 296;
  el("distance-fill").setAttribute("width", String(ratio * 296));
  el("distance-marker").setAttribute("d", "M" + x + " 0v20");
  el("distance-marker").setAttribute("visibility", available ? "visible" : "hidden");
  el("distance-scale").setAttribute("aria-label", available ? "Escala de 0 a 4.000 mm; leitura " + t.distance_mm + " mm" + (t.distance_mm > 4000 ? ", acima da escala" : "") : "Escala de distância: leitura indisponível");
  const now = performance.now();
  recentReadings = recentReadings.filter(point => now - point.at < 30000);
  const values = recentReadings.filter(point => point.value !== null).map(point => point.value);
  const low = values.length ? Math.min(...values) : 0, high = values.length ? Math.max(...values) : 0;
  const span = Math.max(100, high - low), middle = (high + low) / 2;
  let line = "", area = "", segment = [], previous = null, endpoint = null;
  function flush() {
    if (!segment.length) return;
    line += "M" + segment.join("L");
    area += "M" + segment[0][0] + " 78L" + segment.join("L") + "L" + segment[segment.length - 1][0] + " 78Z";
    segment = [];
  }
  if (available) for (const point of recentReadings) {
    if (point.value === null || (previous !== null && point.at - previous >= last.stale_ms)) flush();
    if (point.value !== null) {
      const position = [Number((2 + Math.max(0, 1 - (now - point.at) / 30000) * 296).toFixed(1)), Number((40 - (point.value - middle) / span * 50).toFixed(1))];
      segment.push(position); endpoint = position;
    }
    previous = point.at;
  }
  flush();
  el("trend-line").setAttribute("d", line);
  el("trend-area").setAttribute("d", area);
  el("trend-dot").setAttribute("visibility", endpoint ? "visible" : "hidden");
  if (endpoint) { el("trend-dot").setAttribute("cx", endpoint[0]); el("trend-dot").setAttribute("cy", endpoint[1]); }
  el("tof-trend").setAttribute("aria-label", available && values.length ? values.length + (values.length === 1 ? " leitura válida" : " leituras válidas") + " nos últimos 30 segundos, de " + low + " a " + high + " mm. Escala vertical automática; não representa risco." : "Sem leituras atuais disponíveis");
  text("trend-message", !available ? "Leitura atual indisponível." : values.length < 2 ? "Aguardando a próxima leitura…" : "");
}
