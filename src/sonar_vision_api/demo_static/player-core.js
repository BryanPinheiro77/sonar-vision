"use strict";
(function (root) {
  function atOrBefore(rows, capturedAt) {
    let low = 0, high = rows.length - 1, found = -1;
    while (low <= high) {
      const mid = Math.floor((low + high) / 2);
      if (rows[mid].captured_at_ms <= capturedAt) { found = mid; low = mid + 1; }
      else high = mid - 1;
    }
    return found;
  }
  function tofForFrame(rows, capturedAt) {
    const index = atOrBefore(rows, capturedAt);
    if (index < 0) return {state: "missing", reading: null, age_ms: null};
    const reading = rows[index], age = capturedAt - reading.captured_at_ms;
    return {state: age >= 5000 ? "stale" : reading.valid ? "valid" : "invalid", reading, age_ms: age};
  }
  function frameAt(rows, capturedAt) { return Math.max(0, atOrBefore(rows, capturedAt)); }
  function positionAfter(rows, start, elapsed, speed) {
    if (!rows.length) return {index: -1, ended: true};
    const time = start + Math.max(0, elapsed) * speed;
    return {index: frameAt(rows, time), ended: time >= rows[rows.length - 1].captured_at_ms};
  }
  function timecode(ms) {
    const seconds = Math.max(0, Math.floor(ms / 1000));
    return String(Math.floor(seconds / 60)).padStart(2, "0") + ":" + String(seconds % 60).padStart(2, "0");
  }
  const api = {atOrBefore, tofForFrame, frameAt, positionAfter, timecode};
  root.SonarPlayer = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(globalThis);
