"use strict";
const el = (id) => document.getElementById(id);
const labels = {waiting: "Aguardando dados", receiving: "Recebendo", stale: "Dados atrasados", expired: "Dados expirados", invalid: "Leitura inválida", offline: "Servidor indisponível", paused: "Atualização pausada"};
const quality = {good: "Boa", degraded: "Degradada", invalid: "Inválida"};
const sector = {left: "Esquerda", center: "Centro", right: "Direita", all: "Todos"};
let paused = false, online = false, last = null, fetchedAt = 0, pixels = null, pixelKey = null, objectUrl = null;
let generation = 0, imageFailed = false;
function text(id, value) { el(id).textContent = value; }
function badge(id, state) { text(id, labels[state]); el(id).dataset.state = state; }
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
      ctx.strokeStyle = "#00f5c4"; ctx.lineWidth = 2 * scale;
      ctx.strokeRect(x, y, (x2 - x1) * canvas.width, (y2 - y1) * canvas.height);
      ctx.font = (14 * scale) + "px system-ui";
      const label = box.class_name + " · ID " + (box.track_id ?? "indisponível");
      const top = Math.max(0, y - 24 * scale);
      ctx.fillStyle = "#073b59"; ctx.fillRect(x, top, ctx.measureText(label).width + 12 * scale, 24 * scale);
      ctx.fillStyle = "#ffffff"; ctx.fillText(label, x + 6 * scale, top + 18 * scale);
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
      text("connection", "Servidor conectado · atualização a cada 2 s");
      text("source-kind", next.source.kind === "simulated" ? "FONTE SIMULADA" : "ESP32 · origem configurada pelo operador");
      text("source", "Origem: " + next.source.device_id + " · Sessão: " + next.source.session_id + (next.backend === "simulated" ? " · INFERÊNCIA SIMULADA" : " · Inferência do servidor"));
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
        text("connection", snapshotSucceeded ? "Servidor conectado · JPEG indisponível; nova tentativa em 2 s." : "Falha de atualização. Nova tentativa automática em 2 s.");
        render();
        clearImage("Imagem indisponível nesta atualização. Aguardando o servidor.");
      }
    }
  }
  } finally { setTimeout(update, 2000); }
}
el("boxes").addEventListener("change", draw);
window.addEventListener("resize", draw);
el("pause").addEventListener("click", () => {
  paused = !paused; generation++;
  el("pause").setAttribute("aria-pressed", String(paused));
  text("pause", paused ? "Retomar atualização" : "Pausar atualização");
  if (paused) { text("connection", "Atualização pausada · dados continuam envelhecendo"); clearImage("Atualização pausada. Retome para consultar o servidor."); text("distance", "—"); }
});
setInterval(() => { if (last) { render(); if (paused) text("distance", "—"); } }, 250);
window.addEventListener("pagehide", () => { generation++; clearImage("Página fechada."); last = null; });
update();
